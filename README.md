# append-namespace

Appends Namespace metadata to Kubernetes yaml.

```sh
python3 appendns.py -f argocd.yaml --namespace my-argocd
```

## Features

- append namespace only for `namespaced` resource
- uses k8s api to get resource attributes
- understand introduced CRDs with input yaml

## Example

Before

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  labels:
    app.kubernetes.io/component: server
    app.kubernetes.io/name: argocd-server
    app.kubernetes.io/part-of: argocd
  name: argocd-server
```

👇

After

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  labels:
    app.kubernetes.io/component: server
    app.kubernetes.io/name: argocd-server
    app.kubernetes.io/part-of: argocd
  name: argocd-server
  namespace: argocd # ⭐
```