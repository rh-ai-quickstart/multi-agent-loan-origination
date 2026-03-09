#!/bin/bash
# This project was developed with assistance from AI tools.
#
# Show detailed diagnostics for failed OpenShift deployments.
#
# Env vars (set by Makefile exports):
#   PROJECT_NAME  -- helm release name (default: mortgage-ai)
#   NAMESPACE     -- OpenShift namespace (default: mortgage-ai)
set -euo pipefail

PROJECT_NAME="${PROJECT_NAME:-mortgage-ai}"
NAMESPACE="${NAMESPACE:-$PROJECT_NAME}"

# Helper: run command with oc, fall back to kubectl
kube() {
    oc "$@" 2>/dev/null || kubectl "$@" 2>/dev/null
}

echo "=== Helm Release Status ==="
helm status "$PROJECT_NAME" --namespace "$NAMESPACE" 2>/dev/null \
    || echo "Release not found or not accessible"
echo ""

echo "=== Pod Status ==="
kube get pods -n "$NAMESPACE" || echo "Cannot access pods"
echo ""

echo "=== Failed/CrashLoopBackOff Pods ==="
failed=$(kube get pods -n "$NAMESPACE" -o wide 2>/dev/null \
    | grep -E "(Failed|CrashLoopBackOff|Error|ImagePullBackOff)" || true)
if [ -n "$failed" ]; then
    echo "$failed"
else
    echo "No failed pods found"
fi
echo ""

echo "=== Pod Logs (CrashLoopBackOff pods) ==="
crash_pods=$(kube get pods -n "$NAMESPACE" 2>/dev/null \
    | grep CrashLoopBackOff | awk '{print $1}' || true)
if [ -z "$crash_pods" ]; then
    echo "No CrashLoopBackOff pods found"
else
    for pod_name in $crash_pods; do
        echo "--- Logs for $pod_name ---"
        kube logs -n "$NAMESPACE" "$pod_name" --tail=50 \
            || echo "Cannot access logs for $pod_name"
        echo ""
    done
fi
echo ""

echo "=== Pod Describe (ImagePullBackOff pods) ==="
pull_pods=$(kube get pods -n "$NAMESPACE" 2>/dev/null \
    | grep ImagePullBackOff | awk '{print $1}' || true)
if [ -z "$pull_pods" ]; then
    echo "No ImagePullBackOff pods found"
else
    for pod_name in $pull_pods; do
        echo "--- Describe $pod_name ---"
        kube describe pod -n "$NAMESPACE" "$pod_name" 2>/dev/null | tail -40 \
            || echo "Cannot describe $pod_name"
        echo ""
    done
fi
echo ""

echo "=== Recent Events ==="
kube get events -n "$NAMESPACE" --sort-by='.lastTimestamp' 2>/dev/null | tail -30 \
    || echo "Cannot access events"
echo ""

echo "=== Migration Job Status ==="
kube get jobs -n "$NAMESPACE" -l app.kubernetes.io/component=migration \
    || echo "No migration jobs found"
echo ""

echo "=== Migration Job Pod Logs ==="
migration_pod=$(kube get pods -n "$NAMESPACE" \
    -l app.kubernetes.io/component=migration -o name 2>/dev/null | head -1 || true)
if [ -n "$migration_pod" ]; then
    pod_name="${migration_pod#pod/}"
    echo "Migration pod: $pod_name"
    kube logs -n "$NAMESPACE" "$pod_name" --tail=100 \
        || echo "Cannot access migration logs"
    echo ""
    kube describe pod -n "$NAMESPACE" "$pod_name" 2>/dev/null | tail -40 \
        || echo "Cannot describe migration pod"
else
    echo "No migration pod found"
fi
echo ""

echo "=== Image Pull Issues ==="
kube describe pods -n "$NAMESPACE" 2>/dev/null \
    | grep -B 2 -A 10 -iE "imagepull|errimagepull|imagepullbackoff" \
    || echo "No image pull errors detected"
echo ""

echo "=== Troubleshooting Commands ==="
echo "  Check all resources: oc get all -n $NAMESPACE"
echo "  Check Helm status:   helm status $PROJECT_NAME -n $NAMESPACE"
echo "  View pod logs:       oc logs -n $NAMESPACE <pod-name>"
echo "  Describe pod:        oc describe pod -n $NAMESPACE <pod-name>"
echo "  Check events:        oc get events -n $NAMESPACE --sort-by='.lastTimestamp'"
echo "  Migration logs:      oc logs -n $NAMESPACE -l app.kubernetes.io/component=migration"
