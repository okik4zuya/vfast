import os
import sys


def _run_yt_dlp(argv):
    # Re-entry point for core/download.py's frozen-mode yt-dlp invocation: a PyInstaller
    # onefile exe can't be run as `python -m yt_dlp`, so it re-launches itself with this
    # flag instead. This "import yt_dlp" is also what makes PyInstaller's static analysis
    # trace and bundle the package at all (see hiddenimports in vfast.spec for its plugins).
    import yt_dlp
    sys.exit(yt_dlp.main(argv))


def main():
    if len(sys.argv) > 1:
        project_dir = sys.argv[1]
        if not os.path.isdir(project_dir):
            print(f"Invalid project folder: {project_dir}")
            sys.exit(1)
    else:
        project_dir = os.path.expanduser("~/Videos")
        os.makedirs(project_dir, exist_ok=True)

    import customtkinter as ctk
    from app import App

    ctk.set_appearance_mode("dark")
    ctk.set_default_color_theme("blue")

    app = App()
    app.set_project_dir(project_dir)
    app.mainloop()


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--run-yt-dlp":
        _run_yt_dlp(sys.argv[2:])
    else:
        main()
