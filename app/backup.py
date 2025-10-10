import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

def find_pg_dump_on_windows():
    """
    Tries to find pg_dump.exe by searching the Windows Registry for PostgreSQL installations.
    Returns the full path to pg_dump.exe or None if not found.
    """
    print("Searching for pg_dump.exe in Windows Registry...")
    try:
        import winreg
    except ImportError:
        print("Could not import winreg, skipping registry search.")
        return None

    # List of registry keys to check for PostgreSQL installations
    # We check both 64-bit and 32-bit (Wow6432Node) locations
    registry_paths = [
        r"SOFTWARE\PostgreSQL",
    ]

    for reg_path in registry_paths:
        try:
            # Open the key in read-only mode, checking both 64-bit and 32-bit views
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, reg_path, 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY) as pg_key:
                # Enumerate all subkeys (e.g., 'PostgreSQL 14', 'PostgreSQL 15')
                for i in range(0, winreg.QueryInfoKey(pg_key)[0]):
                    version_key_name = winreg.EnumKey(pg_key, i)
                    with winreg.OpenKey(pg_key, version_key_name) as version_key:
                        try:
                            # Most installers create a 'Base Directory' value
                            base_dir, _ = winreg.QueryValueEx(version_key, "Base Directory")
                            pg_dump_path = Path(base_dir) / "bin" / "pg_dump.exe"
                            if pg_dump_path.is_file():
                                print(f"Found pg_dump.exe at: {pg_dump_path}")
                                return str(pg_dump_path)
                        except FileNotFoundError:
                            # If 'Base Directory' doesn't exist, continue to the next subkey
                            continue
        except FileNotFoundError:
            # If the main 'PostgreSQL' key doesn't exist, continue
            continue
            
    print("Could not find PostgreSQL installation in the registry.")
    return None

# Add the project root to the Python path to allow imports from 'core'
project_root = Path(__file__).resolve().parent
sys.path.insert(0, str(project_root))

try:
    # Reuse the app's settings management to load .env files correctly
    from core.settings import settings
    print("Successfully loaded application settings.")
except ImportError as e:
    print(f"Error: Failed to import application settings. {e}")
    print("Please ensure this script is in the project root and the environment is set up.")
    sys.exit(1)

# --- CONFIGURATION ---
# The backup directory, created inside the project root
BACKUP_DIR = project_root / "backups"
# How many days of backups to keep
DAYS_TO_KEEP = 7
# --- END CONFIGURATION ---

def main():
    """Main function to run the backup process."""
    
    pg_dump_executable = "pg_dump" # Default to PATH
    if sys.platform == "win32":
        print("Attempt 1: Searching Windows Registry...")
        found_path = find_pg_dump_on_windows()
        
        if found_path:
            pg_dump_executable = found_path
        else:
            print("\nAttempt 2: Checking user-provided default path...")
            user_path = Path("C:/Program Files/PostgreSQL/17/bin/pg_dump.exe")
            if user_path.is_file():
                print(f"Found pg_dump.exe at user-provided path: {user_path}")
                pg_dump_executable = str(user_path)
            else:
                print("\nAttempt 3: Falling back to system PATH...")
                pg_dump_executable = "pg_dump"

    print("\nStarting PostgreSQL database backup...")

    # 1. Get DB details from the loaded settings
    db_settings = settings.DB
    db_host = db_settings.HOST
    db_port = db_settings.PORT
    db_name = db_settings.NAME
    db_user = db_settings.USER
    db_password = db_settings.PASSWORD.get_secret_value()

    # 2. Ensure backup directory exists
    BACKUP_DIR.mkdir(exist_ok=True)

    # 3. Create a timestamped filename
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    backup_filename = f"{db_name}_{timestamp}.dump"
    backup_filepath = BACKUP_DIR / backup_filename

    # 4. Set up the pg_dump command and environment
    command = [
        pg_dump_executable,
        f"--host={db_host}",
        f"--port={db_port}",
        f"--username={db_user}",
        "--no-password",
        "--format=c",
        "--blobs",
        f"--file={backup_filepath}",
        db_name,
    ]

    env = os.environ.copy()
    env["PGPASSWORD"] = db_password

    # 5. Execute the command
    print(f"Backing up database '{db_name}' to '{backup_filepath}'...")
    try:
        subprocess.run(
            command,
            capture_output=True,
            text=True,
            env=env,
            check=True, # This will raise CalledProcessError if pg_dump fails
            encoding='utf-8',
        )
        print("\n=== BACKUP SUCCESSFUL ===")
        print(f"Backup file saved to: {backup_filepath}")

    except FileNotFoundError:
        print("\n!!! BACKUP FAILED !!!")
        print(f"Error: '{pg_dump_executable}' command not found.")
        print("Please ensure PostgreSQL client tools are installed and in your system's PATH, or that the script can find it in the registry.")
        sys.exit(1)
    except subprocess.CalledProcessError as e:
        print("\n!!! BACKUP FAILED !!!")
        print(f"pg_dump returned a non-zero exit code: {e.returncode}")
        print(f"Stderr:\n{e.stderr}")
        # Clean up the failed (likely empty) backup file
        if backup_filepath.exists():
            backup_filepath.unlink()
        sys.exit(1)

    # 6. Clean up old backups
    print(f"\nCleaning up backups older than {DAYS_TO_KEEP} days...")
    cutoff_date = datetime.now() - timedelta(days=DAYS_TO_KEEP)
    cleaned_count = 0
    for file in BACKUP_DIR.glob("*.dump"):
        file_mod_time = datetime.fromtimestamp(file.stat().st_mtime)
        if file_mod_time < cutoff_date:
            print(f"Deleting old backup: {file.name}")
            file.unlink()
            cleaned_count += 1
    print(f"Cleanup complete. Deleted {cleaned_count} old backup(s).")

    print("\nBackup process finished.")

if __name__ == "__main__":
    main()
