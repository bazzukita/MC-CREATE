import json
import re
import shutil
import socket
import subprocess
import threading
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import requests

import sys as _sys
# When frozen by PyInstaller, user data lives next to the .exe, not in the temp bundle
if getattr(_sys, "frozen", False):
    BASE_DIR = Path(_sys.executable).parent
    JRE_DIR = Path(_sys._MEIPASS) / "jre"
else:
    BASE_DIR = Path(__file__).parent
    JRE_DIR = BASE_DIR / "jre"

SERVERS_DIR = BASE_DIR / "servers"
CONFIG_FILE = BASE_DIR / "servers.json"
RUNNING_FILE = BASE_DIR / "running.json"

MOJANG_MANIFEST  = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
PAPER_API        = "https://api.papermc.io/v2/projects/paper"
FABRIC_META      = "https://meta.fabricmc.net/v2"
FORGE_PROMOTIONS = "https://files.minecraftforge.net/net/minecraftforge/forge/promotions_slim.json"
FORGE_MAVEN      = "https://maven.minecraftforge.net/net/minecraftforge/forge"
ADOPTIUM_RELEASES_URL = "https://api.adoptium.net/v3/info/available_releases"
ADOPTIUM_ASSET_URL = (
    "https://api.adoptium.net/v3/assets/latest/{version}/hotspot"
    "?architecture=x64&image_type=jre&os=windows&vendor=eclipse"
)
CLASS_FILE_TO_JAVA = {str(44 + i): i for i in range(1, 30)}


class JavaNotFoundError(Exception):
    pass


class JavaVersionError(Exception):
    pass


class ServerManager:
    def __init__(self):
        SERVERS_DIR.mkdir(exist_ok=True)
        self.servers = self._load_config()
        self._processes: dict[str, subprocess.Popen] = {}
        self._orphan_pids: dict[str, int] = {}
        self._java_version_needed = None
        self._restore_running()

    # ── Restore running server from previous session ──────────────────────────

    def _restore_running(self):
        if not RUNNING_FILE.exists():
            return
        try:
            data = json.loads(RUNNING_FILE.read_text(encoding="utf-8"))
            alive = {}
            for name, pid in data.items():
                if name in self.servers and self._pid_alive(pid):
                    self._orphan_pids[name] = pid
                    alive[name] = pid
            if alive:
                RUNNING_FILE.write_text(json.dumps(alive), encoding="utf-8")
            else:
                RUNNING_FILE.unlink(missing_ok=True)
        except Exception:
            pass

    @staticmethod
    def _pid_alive(pid: int) -> bool:
        try:
            import ctypes, ctypes.wintypes
            PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = ctypes.windll.kernel32.OpenProcess(
                PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
            if not handle:
                return False
            code = ctypes.wintypes.DWORD()
            ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
            ctypes.windll.kernel32.CloseHandle(handle)
            return code.value == 259  # STILL_ACTIVE
        except Exception:
            return False

    def _save_running(self):
        data = {name: proc.pid for name, proc in self._processes.items()}
        data.update(self._orphan_pids)
        if data:
            RUNNING_FILE.write_text(json.dumps(data), encoding="utf-8")
        else:
            try:
                RUNNING_FILE.unlink(missing_ok=True)
            except Exception:
                pass

    def _clear_running(self, name: str):
        self._orphan_pids.pop(name, None)
        self._save_running()

    def is_orphan(self, name: str) -> bool:
        return (name not in self._processes
                and name in self._orphan_pids
                and self._pid_alive(self._orphan_pids[name]))

    # ── Config ────────────────────────────────────────────────────────────────

    def _load_config(self):
        if CONFIG_FILE.exists():
            with open(CONFIG_FILE, encoding="utf-8") as f:
                return json.load(f)
        return {}

    def _save_config(self):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(self.servers, f, indent=2)

    # ── Version lists ─────────────────────────────────────────────────────────

    def get_versions(self, server_type="vanilla"):
        if server_type == "vanilla":
            resp = requests.get(MOJANG_MANIFEST, timeout=10)
            resp.raise_for_status()
            releases = [v for v in resp.json()["versions"] if v["type"] == "release"]
            return [{"id": v["id"], "url": v["url"]} for v in releases[:40]]

        elif server_type == "paper":
            resp = requests.get(PAPER_API, timeout=10)
            resp.raise_for_status()
            versions = list(reversed(resp.json()["versions"]))
            return [{"id": v, "url": None} for v in versions[:40]]

        elif server_type == "fabric":
            resp = requests.get(f"{FABRIC_META}/versions/game", timeout=10)
            resp.raise_for_status()
            stable = [v["version"] for v in resp.json() if v.get("stable", False)]
            return [{"id": v, "url": None} for v in stable[:40]]

        elif server_type == "forge":
            resp = requests.get(FORGE_PROMOTIONS, timeout=15)
            resp.raise_for_status()
            promos = resp.json()["promos"]
            mc_versions = sorted(
                {k.rsplit("-", 1)[0] for k in promos.keys()},
                key=lambda v: [int(x) if x.isdigit() else 0 for x in v.split(".")],
                reverse=True,
            )
            return [{"id": v, "url": None} for v in mc_versions[:30]]

        return []

    # ── Download helper ───────────────────────────────────────────────────────

    def _download_file(self, url, dest_path, progress_cb=None, label="Descargando"):
        resp = requests.get(url, stream=True, timeout=600)
        resp.raise_for_status()
        total = int(resp.headers.get("content-length", 0))
        downloaded = 0
        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total:
                    pct = int(downloaded / total * 100)
                    progress_cb(f"{label}... {pct}%")

    # ── Server type installers ────────────────────────────────────────────────

    def _get_jar_url(self, version_url):
        resp = requests.get(version_url, timeout=10)
        resp.raise_for_status()
        return resp.json()["downloads"]["server"]["url"]

    def _download_paper(self, version_id, server_path, progress_cb):
        builds_url = f"{PAPER_API}/versions/{version_id}/builds"
        resp = requests.get(builds_url, timeout=10)
        resp.raise_for_status()
        builds = resp.json()["builds"]
        if not builds:
            raise ValueError(f"No hay builds de Paper disponibles para {version_id}")
        latest = builds[-1]
        build_num = latest["build"]
        jar_name = latest["downloads"]["application"]["name"]
        dl_url = f"{PAPER_API}/versions/{version_id}/builds/{build_num}/downloads/{jar_name}"
        if progress_cb:
            progress_cb(f"Descargando Paper {version_id} (build {build_num})...")
        self._download_file(dl_url, server_path / "paper.jar", progress_cb, "Descargando Paper")
        return "paper.jar"

    def _download_fabric(self, version_id, server_path, progress_cb):
        if progress_cb:
            progress_cb("Obteniendo Fabric Loader más reciente...")
        loader_resp = requests.get(f"{FABRIC_META}/versions/loader/{version_id}", timeout=10)
        loader_resp.raise_for_status()
        loaders = loader_resp.json()
        if not loaders:
            raise ValueError(f"Fabric no soporta Minecraft {version_id}")
        latest_loader = loaders[0]["loader"]["version"]

        installer_resp = requests.get(f"{FABRIC_META}/versions/installer", timeout=10)
        installer_resp.raise_for_status()
        latest_installer = installer_resp.json()[0]["version"]

        dl_url = (
            f"{FABRIC_META}/versions/loader/{version_id}"
            f"/{latest_loader}/{latest_installer}/server/jar"
        )
        if progress_cb:
            progress_cb(f"Descargando Fabric Loader {latest_loader}...")
        self._download_file(
            dl_url, server_path / "fabric-server-launch.jar",
            progress_cb, "Descargando Fabric",
        )
        return "fabric-server-launch.jar"

    def _install_forge(self, version_id, server_path, progress_cb):
        if progress_cb:
            progress_cb("Buscando versión de Forge disponible...")
        resp = requests.get(FORGE_PROMOTIONS, timeout=15)
        resp.raise_for_status()
        promos = resp.json()["promos"]

        forge_ver = promos.get(f"{version_id}-recommended") or promos.get(f"{version_id}-latest")
        if not forge_ver:
            raise ValueError(f"No hay Forge disponible para Minecraft {version_id}")

        full_ver = f"{version_id}-{forge_ver}"
        installer_name = f"forge-{full_ver}-installer.jar"
        dl_url = f"{FORGE_MAVEN}/{full_ver}/{installer_name}"

        installer_path = server_path / installer_name
        if progress_cb:
            progress_cb(f"Descargando instalador Forge {full_ver}...")
        self._download_file(dl_url, installer_path, progress_cb, "Descargando Forge")

        if progress_cb:
            progress_cb("Instalando Forge (puede tardar varios minutos)...")
        java_exe = self._find_java()
        subprocess.run(
            [java_exe, "-jar", installer_name, "--installServer"],
            cwd=str(server_path),
            capture_output=True,
            timeout=600,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )

        try:
            installer_path.unlink()
        except Exception:
            pass

        if progress_cb:
            progress_cb("Buscando archivos del servidor Forge...")

        # Forge 1.17+ — @argfile system
        win_args_list = list(server_path.glob("libraries/net/minecraftforge/forge/*/win_args.txt"))
        if win_args_list:
            rel = str(win_args_list[0].relative_to(server_path)).replace("\\", "/")
            return None, rel

        # Old Forge — universal jar
        forge_jars = [p for p in server_path.glob("forge-*.jar") if "installer" not in p.name]
        if forge_jars:
            forge_jars.sort(key=lambda p: p.stat().st_size, reverse=True)
            return forge_jars[0].name, None

        raise ValueError(
            "Forge se instaló pero no se encontró el ejecutable del servidor. "
            "Abre la carpeta del servidor para verificar los archivos."
        )

    # ── Create server ─────────────────────────────────────────────────────────

    def create_server(self, name, version_id, server_type="vanilla", version_url=None,
                      ram_mb=1024, cores=None, progress_cb=None):
        server_path = SERVERS_DIR / name
        server_path.mkdir(exist_ok=True)

        jar_name = "server.jar"
        forge_win_args = None

        if server_type == "vanilla":
            if progress_cb:
                progress_cb("Obteniendo URL del servidor...")
            jar_url = self._get_jar_url(version_url)
            if progress_cb:
                progress_cb("Descargando server.jar...")
            self._download_file(jar_url, server_path / "server.jar", progress_cb, "Descargando")

        elif server_type == "paper":
            jar_name = self._download_paper(version_id, server_path, progress_cb)

        elif server_type == "fabric":
            jar_name = self._download_fabric(version_id, server_path, progress_cb)

        elif server_type == "forge":
            jar_name, forge_win_args = self._install_forge(version_id, server_path, progress_cb)

        (server_path / "eula.txt").write_text("eula=true\n")

        config_data = {
            "name": name,
            "version": version_id,
            "server_type": server_type,
            "jar_name": jar_name,
            "path": str(server_path),
            "ram": ram_mb,
            "cores": cores,
        }
        if forge_win_args:
            config_data["forge_win_args"] = forge_win_args

        self.servers[name] = config_data
        self._save_config()

        if progress_cb:
            progress_cb("¡Servidor creado correctamente!")
        return self.servers[name]

    # ── Start / stop ──────────────────────────────────────────────────────────

    def start_server(self, name, output_cb=None):
        if self.is_running(name):
            return False

        config = self.servers[name]
        ram = config.get("ram", 1024)
        server_type = config.get("server_type", "vanilla")
        jar_name = config.get("jar_name", "server.jar")
        forge_win_args = config.get("forge_win_args")
        java_exe = self._find_java()

        port = config.get("port", 25565)
        props = Path(config["path"]) / "server.properties"
        if props.exists():
            self.update_port(name, port)

        cores = config.get("cores")

        if forge_win_args:
            # Forge 1.17+ — update user_jvm_args.txt and use @argfile
            jvm_file = Path(config["path"]) / "user_jvm_args.txt"
            lines = [f"-Xmx{ram}M", f"-Xms{ram}M"]
            if cores:
                lines.append(f"-XX:ActiveProcessorCount={cores}")
            jvm_file.write_text("\n".join(lines) + "\n")
            cmd = [java_exe, "@user_jvm_args.txt", f"@{forge_win_args}", "nogui"]
        else:
            cmd = [java_exe, f"-Xmx{ram}M", f"-Xms{ram}M"]
            if cores:
                cmd.append(f"-XX:ActiveProcessorCount={cores}")
            nogui = "nogui" if server_type == "fabric" else "--nogui"
            cmd += ["-jar", jar_name or "server.jar", nogui]

        proc = subprocess.Popen(
            cmd,
            cwd=config["path"],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
            creationflags=subprocess.CREATE_NO_WINDOW,
        )
        self._processes[name] = proc
        self._orphan_pids.pop(name, None)
        self._save_running()

        if output_cb:
            threading.Thread(
                target=self._read_output, args=(name, proc, output_cb), daemon=True
            ).start()

        return True

    def _read_output(self, name, proc, output_cb):
        for raw in iter(proc.stdout.readline, b""):
            line = raw.decode("utf-8", errors="replace")
            output_cb(line)
            if "UnsupportedClassVersionError" in line:
                m = re.search(r"class file version (\d+)", line)
                if m:
                    cf = m.group(1)
                    self._java_version_needed = CLASS_FILE_TO_JAVA.get(cf, int(cf) - 44)
        try:
            proc.wait(timeout=10)
        except Exception:
            pass
        for s in (proc.stdin, proc.stdout):
            try:
                if s:
                    s.close()
            except Exception:
                pass
        self._processes.pop(name, None)
        self._clear_running(name)
        output_cb("[MC Create] El proceso del servidor ha terminado.\n")

    def stop_server(self, name):
        proc = self._processes.get(name)
        if proc and proc.poll() is None:
            try:
                proc.stdin.write(b"stop\n")
                proc.stdin.flush()
            except Exception:
                pass

    def kill_server(self, name):
        proc = self._processes.get(name)
        if proc and proc.poll() is None:
            proc.kill()
        elif name in self._orphan_pids:
            subprocess.run(
                ["taskkill", "/PID", str(self._orphan_pids[name]), "/F"],
                capture_output=True,
                creationflags=subprocess.CREATE_NO_WINDOW,
            )
            self._orphan_pids.pop(name, None)
            self._save_running()

    def send_command(self, name, command):
        proc = self._processes.get(name)
        if proc and proc.poll() is None:
            try:
                proc.stdin.write((command + "\n").encode("utf-8"))
                proc.stdin.flush()
            except Exception:
                pass

    def is_running(self, name: str) -> bool:
        proc = self._processes.get(name)
        if proc is not None and proc.poll() is None:
            return True
        if name in self._orphan_pids and self._pid_alive(self._orphan_pids[name]):
            return True
        return False

    def get_running_servers(self) -> list[str]:
        running = [n for n, p in self._processes.items() if p.poll() is None]
        running += [n for n in self._orphan_pids if n not in running and self._pid_alive(self._orphan_pids[n])]
        return running

    # ── Server list ───────────────────────────────────────────────────────────

    def list_servers(self):
        return list(self.servers.values())

    def get_port(self, name):
        return self.servers[name].get("port", 25565)

    def update_ram(self, name: str, ram_mb: int):
        self.servers[name]["ram"] = ram_mb
        self._save_config()

    def update_cores(self, name: str, cores):
        self.servers[name]["cores"] = cores
        self._save_config()

    def update_port(self, name, port: int):
        self.servers[name]["port"] = port
        self._save_config()
        props = Path(self.servers[name]["path"]) / "server.properties"
        if props.exists():
            content = props.read_text(encoding="utf-8")
            if re.search(r"^server-port=", content, re.MULTILINE):
                content = re.sub(r"(?m)^server-port=\d+", f"server-port={port}", content)
            else:
                content += f"\nserver-port={port}\n"
            props.write_text(content, encoding="utf-8")

    @staticmethod
    def get_local_ip():
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except Exception:
            return "127.0.0.1"

    def delete_server(self, name):
        if name in self.servers:
            path = Path(self.servers[name]["path"])
            if path.exists():
                shutil.rmtree(path)
            del self.servers[name]
            self._save_config()

    # ── Server properties ────────────────────────────────────────────────────

    def read_properties(self, name: str) -> dict:
        props = {}
        path = Path(self.servers[name]["path"]) / "server.properties"
        if not path.exists():
            return props
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                props[k.strip()] = v.strip()
        return props

    def write_properties(self, name: str, updates: dict):
        path = Path(self.servers[name]["path"]) / "server.properties"
        if not path.exists():
            return
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        written = set()
        result = []
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, _ = stripped.partition("=")
                k = k.strip()
                if k in updates:
                    result.append(f"{k}={updates[k]}")
                    written.add(k)
                    continue
            result.append(line)
        for k, v in updates.items():
            if k not in written:
                result.append(f"{k}={v}")
        path.write_text("\n".join(result) + "\n", encoding="utf-8")

    # ── Players ───────────────────────────────────────────────────────────────

    def _rjson(self, path: Path):
        if path.exists():
            try:
                return json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return []

    def _wjson(self, path: Path, data):
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")

    def get_players(self, name: str) -> list:
        base      = Path(self.servers[name]["path"])
        whitelist = {p["uuid"]: p for p in self._rjson(base / "whitelist.json")}
        ops       = {p["uuid"]: p for p in self._rjson(base / "ops.json")}
        banned    = {p["uuid"]: p for p in self._rjson(base / "banned-players.json")}
        cache     = self._rjson(base / "usercache.json")

        players: dict = {}
        for p in cache:
            uid, pname = p.get("uuid", ""), p.get("name", "")
            if uid and pname:
                players[uid] = {"uuid": uid, "name": pname}
        for d in (whitelist, ops, banned):
            for uid, p in d.items():
                if uid not in players and p.get("name"):
                    players[uid] = {"uuid": uid, "name": p["name"]}

        stats_dir = base / "world" / "players" / "stats"
        result = []
        for uid, p in players.items():
            hours = 0.0
            sf = stats_dir / f"{uid}.json"
            if sf.exists():
                try:
                    ticks = (json.loads(sf.read_text(encoding="utf-8"))
                             .get("stats", {})
                             .get("minecraft:custom", {})
                             .get("minecraft:play_time", 0))
                    hours = ticks / 72000
                except Exception:
                    pass
            result.append({
                "uuid":        uid,
                "name":        p["name"],
                "hours":       hours,
                "whitelisted": uid in whitelist,
                "op":          uid in ops,
                "banned":      uid in banned,
            })
        result.sort(key=lambda x: x["name"].lower())
        return result

    def whitelist_add(self, server_name: str, uuid: str, player_name: str):
        base = Path(self.servers[server_name]["path"])
        wl   = self._rjson(base / "whitelist.json")
        if not any(p["uuid"] == uuid for p in wl):
            wl.append({"uuid": uuid, "name": player_name})
            self._wjson(base / "whitelist.json", wl)
        if self.is_running() and self.get_active_server() == server_name:
            self.send_command("whitelist reload")

    def whitelist_remove(self, server_name: str, uuid: str):
        base = Path(self.servers[server_name]["path"])
        self._wjson(base / "whitelist.json",
                    [p for p in self._rjson(base / "whitelist.json") if p["uuid"] != uuid])
        if self.is_running() and self.get_active_server() == server_name:
            self.send_command("whitelist reload")

    def op_add(self, server_name: str, uuid: str, player_name: str):
        base = Path(self.servers[server_name]["path"])
        ops  = self._rjson(base / "ops.json")
        if not any(p["uuid"] == uuid for p in ops):
            ops.append({"uuid": uuid, "name": player_name,
                        "level": 4, "bypassesPlayerLimit": False})
            self._wjson(base / "ops.json", ops)
        if self.is_running() and self.get_active_server() == server_name:
            self.send_command(f"op {player_name}")

    def op_remove(self, server_name: str, uuid: str, player_name: str):
        base = Path(self.servers[server_name]["path"])
        self._wjson(base / "ops.json",
                    [p for p in self._rjson(base / "ops.json") if p["uuid"] != uuid])
        if self.is_running() and self.get_active_server() == server_name:
            self.send_command(f"deop {player_name}")

    def ban_player(self, server_name: str, uuid: str, player_name: str):
        base   = Path(self.servers[server_name]["path"])
        banned = self._rjson(base / "banned-players.json")
        if not any(p["uuid"] == uuid for p in banned):
            banned.append({
                "uuid": uuid, "name": player_name,
                "created": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S +0000"),
                "source": "MC Create", "expires": "forever",
                "reason": "Baneado por un operador.",
            })
            self._wjson(base / "banned-players.json", banned)
        if self.is_running() and self.get_active_server() == server_name:
            self.send_command(f"ban {player_name}")

    def unban_player(self, server_name: str, uuid: str, player_name: str):
        base = Path(self.servers[server_name]["path"])
        self._wjson(base / "banned-players.json",
                    [p for p in self._rjson(base / "banned-players.json") if p["uuid"] != uuid])
        if self.is_running() and self.get_active_server() == server_name:
            self.send_command(f"pardon {player_name}")

    # ── Mods ─────────────────────────────────────────────────────────────────

    def list_mods(self, name):
        mods_dir = Path(self.servers[name]["path"]) / "mods"
        if not mods_dir.exists():
            return []
        return sorted(f.name for f in mods_dir.glob("*.jar"))

    def install_mod(self, name, jar_path):
        mods_dir = Path(self.servers[name]["path"]) / "mods"
        mods_dir.mkdir(exist_ok=True)
        dest = mods_dir / Path(jar_path).name
        shutil.copy2(jar_path, dest)
        return dest.name

    def remove_mod(self, name, mod_name):
        mod_path = Path(self.servers[name]["path"]) / "mods" / mod_name
        if mod_path.exists():
            mod_path.unlink()

    # ── Backups ───────────────────────────────────────────────────────────────

    def create_backup(self, name: str, auto: bool = False, progress_cb=None) -> str:
        """Zip world + config files. auto=True overwrites auto_backup.zip."""
        server_path = Path(self.servers[name]["path"])
        backup_dir = server_path / "backups"
        backup_dir.mkdir(exist_ok=True)

        if auto:
            zip_name = "auto_backup.zip"
        else:
            ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
            zip_name = f"backup_{ts}.zip"

        zip_path = backup_dir / zip_name

        # What to include: world dirs + root config files
        to_zip = []
        for world_dir in ("world", "world_nether", "world_the_end"):
            wd = server_path / world_dir
            if wd.is_dir():
                to_zip.append(wd)
        for fname in ("server.properties", "whitelist.json", "ops.json",
                      "banned-players.json", "usercache.json", "eula.txt"):
            fp = server_path / fname
            if fp.exists():
                to_zip.append(fp)

        if not to_zip:
            raise FileNotFoundError(
                "No hay datos que respaldar. Inicia el servidor al menos una vez."
            )

        total_files = sum(
            sum(1 for _ in p.rglob("*") if _.is_file()) if p.is_dir() else 1
            for p in to_zip
        )
        done = 0

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as zf:
            for item in to_zip:
                if item.is_dir():
                    for fp in item.rglob("*"):
                        if fp.is_file():
                            try:
                                zf.write(fp, fp.relative_to(server_path))
                            except (PermissionError, OSError):
                                pass  # skip locked files (session.lock, etc.)
                            done += 1
                            if progress_cb and total_files:
                                progress_cb(int(done / total_files * 100))
                else:
                    try:
                        zf.write(item, item.relative_to(server_path))
                    except (PermissionError, OSError):
                        pass
                    done += 1

        return zip_name

    def list_backups(self, name: str) -> list:
        backup_dir = Path(self.servers[name]["path"]) / "backups"
        if not backup_dir.is_dir():
            return []
        result = []
        for f in backup_dir.glob("*.zip"):
            stat = f.stat()
            result.append({
                "name":  f.name,
                "size":  stat.st_size,
                "mtime": stat.st_mtime,
                "auto":  f.name == "auto_backup.zip",
            })
        result.sort(key=lambda x: x["mtime"], reverse=True)
        return result

    def restore_backup(self, name: str, backup_name: str):
        """Replace world + config files from backup zip."""
        server_path = Path(self.servers[name]["path"])
        zip_path    = server_path / "backups" / backup_name
        if not zip_path.exists():
            raise FileNotFoundError(f"Backup no encontrado: {backup_name}")

        # Remove existing world dirs before extracting
        for world_dir in ("world", "world_nether", "world_the_end"):
            wd = server_path / world_dir
            if wd.is_dir():
                shutil.rmtree(wd)

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(server_path)

    def delete_backup(self, name: str, backup_name: str):
        path = Path(self.servers[name]["path"]) / "backups" / backup_name
        if path.exists():
            path.unlink()

    def get_auto_backup_hours(self, name: str) -> int:
        return self.servers[name].get("auto_backup_hours", 0)

    def set_auto_backup_hours(self, name: str, hours: int):
        self.servers[name]["auto_backup_hours"] = hours
        self._save_config()

    # ── Java detection ────────────────────────────────────────────────────────

    def check_java(self):
        java_exe = self._find_java()
        self._check_java_version(java_exe)
        return java_exe

    def java_is_ready(self):
        try:
            self.check_java()
            return True
        except (JavaNotFoundError, JavaVersionError):
            return False

    @staticmethod
    def _find_java():
        if JRE_DIR.exists():
            local = sorted(JRE_DIR.rglob("java.exe"), key=lambda p: str(p), reverse=True)
            if local:
                return str(local[0])

        for candidate in ["java", "javaw"]:
            try:
                result = subprocess.run([candidate, "-version"], capture_output=True, timeout=5)
                if result.returncode == 0 or result.stderr:
                    return candidate
            except FileNotFoundError:
                continue

        search_roots = [
            Path("C:/Program Files/Eclipse Adoptium"),
            Path("C:/Program Files/Java"),
            Path("C:/Program Files/Eclipse Foundation"),
            Path("C:/Program Files/Microsoft"),
            Path("C:/Program Files/Zulu"),
            Path("C:/Program Files/BellSoft"),
        ]
        candidates = []
        for root in search_roots:
            if root.exists():
                candidates.extend(root.rglob("java.exe"))

        if candidates:
            candidates.sort(key=lambda p: str(p), reverse=True)
            return str(candidates[0])

        raise JavaNotFoundError("Java no encontrado.")

    @staticmethod
    def _check_java_version(java_exe):
        result = subprocess.run([java_exe, "-version"], capture_output=True, text=True, timeout=5)
        output = result.stderr or result.stdout
        m = re.search(r'version "(\d+)', output)
        if m:
            major = int(m.group(1))
            if major == 1:
                m2 = re.search(r'version "1\.(\d+)', output)
                major = int(m2.group(1)) if m2 else major
            if major < 17:
                raise JavaVersionError(
                    f"Java {major} detectado. Se necesita Java 17 o superior."
                )

    # ── Java auto-download ────────────────────────────────────────────────────

    def download_java(self, progress_cb=None, version=None):
        if progress_cb:
            progress_cb("Consultando versiones disponibles de Java...")

        if version is None:
            r = requests.get(ADOPTIUM_RELEASES_URL, timeout=15)
            r.raise_for_status()
            data = r.json()
            version = self._java_version_needed or data.get("most_recent_lts", 21)

        asset_url = ADOPTIUM_ASSET_URL.format(version=version)
        resp = requests.get(asset_url, timeout=15)
        resp.raise_for_status()
        package = resp.json()[0]["binary"]["package"]
        dl_url = package["link"]
        total = package.get("size", 0)

        if progress_cb:
            mb = total / 1024 / 1024
            progress_cb(f"Descargando Java {version} JRE ({mb:.0f} MB)...")

        zip_path = BASE_DIR / "_java_download.zip"
        downloaded = 0

        resp = requests.get(dl_url, stream=True, timeout=600)
        resp.raise_for_status()

        with open(zip_path, "wb") as f:
            for chunk in resp.iter_content(65536):
                f.write(chunk)
                downloaded += len(chunk)
                if progress_cb and total:
                    pct = int(downloaded / total * 100)
                    progress_cb(f"Descargando Java {version} JRE... {pct}%")

        if progress_cb:
            progress_cb("Extrayendo Java...")

        if JRE_DIR.exists():
            shutil.rmtree(JRE_DIR)
        JRE_DIR.mkdir()

        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(JRE_DIR)

        zip_path.unlink()
        self._java_version_needed = None

        if progress_cb:
            progress_cb(f"Java {version} instalado correctamente.")
