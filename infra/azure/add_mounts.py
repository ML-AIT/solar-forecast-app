"""Add the Azure Files mounts to a YAML exported from Azure, ready for `az ... update --yaml`.

The CLI has no flags for volumes, so the steps are: export, add the mounts here, update.

    uv run --no-project --with pyyaml python infra/azure/add_mounts.py job <exported.yaml> <out.yaml>
    uv run --no-project --with pyyaml python infra/azure/add_mounts.py api <exported.yaml> <out.yaml>

job: models read only, forecasts read and write. api: forecasts read only, FORECAST_PROVIDER=file.

Azure Files mounts are owned by root unless told otherwise, and both images run as uid 10001.
"""

import sys

import yaml

OWNER = "uid=10001,gid=10001"
READ_ONLY = f"{OWNER},dir_mode=0550,file_mode=0440"
READ_WRITE = f"{OWNER},dir_mode=0750,file_mode=0640"

MOUNTS = {
    "job": [("models", "models-ro", "/models", READ_ONLY),
            ("forecasts", "forecasts-rw", "/forecasts", READ_WRITE)],
    "api": [("forecasts", "forecasts-ro", "/forecasts", READ_ONLY)],
}
ENV = {"job": {}, "api": {"FORECAST_PROVIDER": "file", "FORECAST_DIR": "/forecasts"}}


def add_mounts(spec: dict, kind: str) -> dict:
    template = spec["properties"]["template"]
    container = template["containers"][0]
    template["volumes"] = [
        {"name": name, "storageType": "AzureFile", "storageName": storage, "mountOptions": options}
        for name, storage, _, options in MOUNTS[kind]]
    container["volumeMounts"] = [
        {"volumeName": name, "mountPath": path} for name, _, path, _ in MOUNTS[kind]]
    env = {e["name"]: e for e in container.get("env") or []}
    env.update({name: {"name": name, "value": value} for name, value in ENV[kind].items()})
    container["env"] = list(env.values())
    return spec


if __name__ == "__main__":
    kind, source, target = sys.argv[1:]
    with open(source, encoding="utf-8") as f:
        spec = yaml.safe_load(f)
    with open(target, "w", encoding="utf-8") as f:
        yaml.safe_dump(add_mounts(spec, kind), f, sort_keys=False)
