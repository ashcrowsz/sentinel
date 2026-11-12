"""Run model-generated code in a locked-down Kubernetes Job.

Generated code is untrusted code: non-root, read-only root fs, no egress
(NetworkPolicy in the Helm chart), hard CPU/RAM/time limits.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_DNS = re.compile(r"[^a-z0-9-]")


@dataclass(frozen=True)
class SandboxSpec:
    repo_url: str
    sha: str
    patch_configmap: str
    test_command: str = "pytest -q -x"
    image: str = "python:3.12-slim"
    namespace: str = "sentinel-sandbox"
    cpu: str = "2"
    memory: str = "2Gi"
    deadline_seconds: int = 300


def job_name(repo: str, sha: str, attempt: int) -> str:
    base = _DNS.sub("-", f"sbx-{repo.split('/')[-1].lower()}-{sha[:8]}-{attempt}")
    return base[:63].strip("-")


def build_job_manifest(spec: SandboxSpec, name: str) -> dict[str, Any]:
    # the clone already happened in the init container; this one has no network
    script = (
        "set -euo pipefail; cd /work/repo && "
        f"git checkout --quiet {spec.sha} && git apply /patch/patch.diff && "
        f"{spec.test_command}"
    )
    return {
        "apiVersion": "batch/v1",
        "kind": "Job",
        "metadata": {
            "name": name,
            "namespace": spec.namespace,
            "labels": {"app.kubernetes.io/part-of": "sentinel", "sentinel/role": "sandbox"},
        },
        "spec": {
            "backoffLimit": 0,
            "activeDeadlineSeconds": spec.deadline_seconds,
            "ttlSecondsAfterFinished": 600,
            "template": {
                "metadata": {"labels": {"sentinel/role": "sandbox"}},
                "spec": {
                    "restartPolicy": "Never",
                    "automountServiceAccountToken": False,
                    "securityContext": {
                        "runAsNonRoot": True,
                        "runAsUser": 10001,
                        "seccompProfile": {"type": "RuntimeDefault"},
                    },
                    # clone happens in an init container that is allowed egress to github.com only
                    "initContainers": [
                        {
                            "name": "fetch",
                            "image": "alpine/git:2.45.2",
                            "command": [
                                "sh", "-c",
                                f"git clone --quiet {spec.repo_url} /work/repo && "
                                "pip download --quiet -d /work/wheels -r /work/repo/requirements.txt",
                            ],
                            "volumeMounts": [{"name": "work", "mountPath": "/work"}],
                        }
                    ],
                    "containers": [
                        {
                            "name": "tests",
                            "image": spec.image,
                            "command": [
                                "bash", "-c",
                                "pip install --quiet --no-index -f /work/wheels "
                                "-r /work/repo/requirements.txt && " + script,
                            ],
                            "resources": {
                                "requests": {"cpu": spec.cpu, "memory": spec.memory},
                                "limits": {"cpu": spec.cpu, "memory": spec.memory},
                            },
                            "securityContext": {
                                "allowPrivilegeEscalation": False,
                                "capabilities": {"drop": ["ALL"]},
                            },
                            "volumeMounts": [
                                {"name": "work", "mountPath": "/work"},
                                {"name": "patch", "mountPath": "/patch", "readOnly": True},
                            ],
                        }
                    ],
                    "volumes": [
                        {"name": "work", "emptyDir": {"sizeLimit": "1Gi"}},
                        {"name": "patch", "configMap": {"name": spec.patch_configmap}},
                    ],
                },
            },
        },
    }
