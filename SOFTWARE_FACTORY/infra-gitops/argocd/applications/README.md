# ==============================================================================
# Applications Directory
# ==============================================================================
# Este directorio está VACÍO intencionalmente.
# 
# Las aplicaciones se gestionan AUTOMÁTICAMENTE via ApplicationSets en:
#   argocd/applicationsets/apps-generator.yaml
#
# El ApplicationSet detecta automáticamente todas las carpetas en:
#   apps/*/overlays/dev  → Crea Application nombre-app-dev
#   apps/*/overlays/prod → Crea Application nombre-app-prod
#
# Para agregar una nueva aplicación:
#   1. Crear carpeta apps/mi-app/base/
#   2. Crear overlays apps/mi-app/overlays/dev/ y /prod/
#   3. Push a git → ArgoCD la detecta y despliega automáticamente
#
# ==============================================================================
# Si necesitas una Application MANUAL (no auto-descubierta), crea un .yaml aquí
# siguiendo este ejemplo:
#
# apiVersion: argoproj.io/v1alpha1
# kind: Application
# metadata:
#   name: mi-app-especial
#   namespace: argocd
# spec:
#   project: software-factory
#   source:
#     repoURL: https://bitbucket.org/software-factory-iot/infra-gitops.git
#     targetRevision: HEAD
#     path: apps/mi-app/overlays/prod
#   destination:
#     server: https://kubernetes.default.svc
#     namespace: prod
#   syncPolicy:
#     automated:
#       prune: true
#       selfHeal: true
# ==============================================================================
