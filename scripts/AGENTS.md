# Scripts

Start and stop the app container. Both pairs use image `pm-app` and container `pm-app`,
resolve the repository root from the script location, and can be run from any directory.

| Platform   | Start                                | Stop                                |
|------------|--------------------------------------|-------------------------------------|
| Mac, Linux | `bash scripts/start.sh`              | `bash scripts/stop.sh`              |
| Windows    | `powershell -File scripts\start.ps1` | `powershell -File scripts\stop.ps1` |

## Behavior

- Start: `docker build -t pm-app <repo root>`, removes any existing `pm-app` container,
  then `docker run -d --name pm-app -p 8000:8000 pm-app`. Adds `--env-file <repo root>/.env`
  only if that file exists. App is at http://localhost:8000.
- Stop: removes the `pm-app` container if it exists; otherwise prints that it is not
  running and exits successfully.

Requires Docker on PATH.

## Verification

- Windows: `start.ps1` and `stop.ps1` were run successfully with Docker. Start built the
  image and ran the container; `/` and `/api/health` returned 200. Stop removed the
  container, a second stop while absent exited successfully, a restart served both routes
  again, and a final stop left no container.
- Mac and Linux: `start.sh` and `stop.sh` pass `bash -n` but have not been run on those
  platforms.
