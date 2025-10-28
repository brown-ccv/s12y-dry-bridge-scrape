# Docker Deployment

## Quick Start

```bash
docker build -t dry-bridge-refresh:latest .
docker run --rm --env-file .env.local dry-bridge-refresh:latest
```

## Build Options

```bash
docker build --platform linux/amd64 -t dry-bridge-refresh:latest .
docker buildx build --platform linux/amd64,linux/arm64 -t registry.com/dry-bridge-refresh:v0.1.0 --push .
```

## Kubernetes CronJob

```yaml
apiVersion: batch/v1
kind: CronJob
metadata:
  name: dry-bridge-refresh
  namespace: solar-data
spec:
  schedule: "*/15 * * * *"
  concurrencyPolicy: Forbid
  successfulJobsHistoryLimit: 3
  failedJobsHistoryLimit: 3
  jobTemplate:
    spec:
      template:
        spec:
          restartPolicy: OnFailure
          containers:
          - name: refresh
            image: registry.com/dry-bridge-refresh:v0.1.0
            envFrom:
            - secretRef:
                name: dry-bridge-db-credentials
            env:
            - name: MAX_FETCH_ATTEMPTS
              value: "5"
            resources:
              requests:
                memory: "256Mi"
                cpu: "100m"
              limits:
                memory: "512Mi"
                cpu: "500m"
            securityContext:
              runAsNonRoot: true
              runAsUser: 1000
              allowPrivilegeEscalation: false
              readOnlyRootFilesystem: true
```

Create secret:
```bash
kubectl create secret generic dry-bridge-db-credentials \
  --namespace=solar-data \
  --from-literal=DB_HOST='your-db-host' \
  --from-literal=DB_PORT='5432' \
  --from-literal=DB_NAME='dry_bridge_db' \
  --from-literal=DB_USER='your_user' \
  --from-literal=DB_PASSWORD='your_password'
```

## Troubleshooting

```bash
# View logs
kubectl logs -n solar-data job/dry-bridge-refresh-<timestamp>

# Debug
docker run -it --rm --entrypoint /bin/bash --env-file .env.local dry-bridge-refresh:latest
```
