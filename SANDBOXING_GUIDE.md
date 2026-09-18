# Agents Office: Sandboxing & Security Guide

How to safely isolate agent tool execution for your custom agents-office implementation.

---

## The Problem

In current agents-office, agents execute Claude-generated tool calls directly:

```
Agent generates: "Call Gmail to send email"
  ↓
Claude CLI subprocess runs in shared environment
  ↓
Has direct MCP server access
  ↓
Risk: Corrupted prompt → agent sends unintended email
```

**Sandboxing moves the risk boundary:**

```
Agent generates: "Call Gmail to send email"
  ↓
Tool call → JSON → Sandbox (isolated container/process)
  ↓
Sandbox validates against whitelist
  ↓
Only whitelisted action allowed
  ↓
Result → back to agent
```

---

## Three Sandboxing Approaches

### Approach 1: Subprocess Isolation (Light, Development)

**Pros:**
- No extra infrastructure
- Easy to test locally
- Low latency (5-50ms overhead)

**Cons:**
- Kernel escape possible (rare, but possible)
- Resource limits harder to enforce
- No true isolation of filesystem

**When to use:** Development, demos, internal tools with trusted networks

**Setup:**

```python
# agents-office-langgraph/sandbox/subprocess_sandbox.py
import subprocess
import json
import os
from pathlib import Path

class SubprocessSandbox:
    """Execute tool calls in isolated subprocess"""
    
    TOOL_WHITELIST = {
        'gmail': ['send', 'read', 'draft'],
        'slack': ['send_message', 'read_channel'],
        'notion': ['read_page', 'append_block'],
        'google_drive': ['list_files', 'read_file'],
        'web': ['search'],
    }
    
    def __init__(self, config):
        self.config = config
        self.temp_dir = Path(config.get('sandbox_temp', '/tmp/agents-office-tools'))
        self.temp_dir.mkdir(exist_ok=True)
    
    async def execute(self, tool_call: dict, agent_id: str, task_id: str) -> str:
        """Execute tool in subprocess with timeout"""
        
        # 1. Validate
        tool_name = tool_call['tool']
        if tool_name not in self.TOOL_WHITELIST:
            raise ValueError(f'Tool {tool_name} not allowed')
        
        allowed_actions = self.TOOL_WHITELIST[tool_name]
        action = tool_call.get('action')
        if action and action not in allowed_actions:
            raise ValueError(f'Action {action} not allowed for {tool_name}')
        
        # 2. Prepare sandbox environment
        sandbox_env = os.environ.copy()
        sandbox_env.pop('ANTHROPIC_API_KEY', None)  # Don't pass secrets
        sandbox_env['TASK_ID'] = task_id
        sandbox_env['AGENT_ID'] = agent_id
        
        # 3. Create tool invocation file
        tool_file = self.temp_dir / f'{task_id}-{tool_name}.json'
        tool_file.write_text(json.dumps({
            'tool': tool_name,
            'input': tool_call.get('input', {}),
            'allowed_actions': allowed_actions
        }))
        
        # 4. Run in subprocess
        try:
            result = subprocess.run(
                ['python', '-m', 'agents_office.sandbox.tool_runner',
                 '--file', str(tool_file),
                 '--tool', tool_name],
                capture_output=True,
                text=True,
                timeout=30,
                env=sandbox_env,
                cwd=str(self.temp_dir)
            )
            
            if result.returncode != 0:
                raise RuntimeError(f'Tool execution failed: {result.stderr}')
            
            # 5. Return result
            output = json.loads(result.stdout)
            return output.get('result', '')
            
        except subprocess.TimeoutExpired:
            raise RuntimeError(f'Tool {tool_name} exceeded 30s timeout')
        finally:
            # Cleanup
            tool_file.unlink(missing_ok=True)

# Module entry point
if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--file')
    parser.add_argument('--tool')
    args = parser.parse_args()
    
    tool_config = json.loads(Path(args.file).read_text())
    
    # Execute tool
    # (Gmail, Slack, etc. — only the specific action)
    result = execute_tool_safely(tool_config)
    print(json.dumps({'result': result}))
```

### Approach 2: Container Isolation (Production-Ready)

**Pros:**
- True OS-level isolation
- Filesystem + network policies
- Easy to scale with Kubernetes
- Industry standard (Docker)

**Cons:**
- Extra infrastructure
- Container startup latency (500ms-2s)
- Need container orchestration

**When to use:** Production, untrusted users, sensitive operations

**Setup:**

```dockerfile
# Dockerfile
FROM python:3.11-slim

# Minimal base: no build tools, no shell history
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

WORKDIR /agent

# Copy only what's needed
COPY sandbox/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Create non-root user
RUN useradd -m -s /sbin/nologin agent
USER agent

# Read-only filesystem (except /tmp)
VOLUME ["/agent/workspace", "/agent/logs"]

# Entrypoint
COPY sandbox/entrypoint.py .
ENTRYPOINT ["python", "entrypoint.py"]
```

**Python wrapper:**

```python
# agents-office-langgraph/sandbox/container_sandbox.py
import docker
import json
from typing import Dict

class ContainerSandbox:
    """Execute tools in Docker containers"""
    
    def __init__(self, config):
        self.client = docker.from_env()
        self.image = config.get('sandbox_image', 'agents-office-sandbox:latest')
        self.network = config.get('sandbox_network', 'agents-office-net')
    
    async def execute(self, tool_call: dict, agent_id: str, task_id: str) -> str:
        """Execute in container"""
        
        container = self.client.containers.run(
            self.image,
            [
                '--tool', tool_call['tool'],
                '--input', json.dumps(tool_call.get('input', {})),
                '--agent', agent_id
            ],
            network=self.network,
            mem_limit='256m',  # 256 MB max
            memswap_limit='512m',  # 512 MB with swap
            cpus='1.0',  # 1 CPU max
            read_only=True,  # immutable FS except /tmp
            volumes={
                '/tmp': {'bind': '/tmp', 'mode': 'rw'},
                '/agent/workspace': {'bind': '/agent/workspace', 'mode': 'rw'}
            },
            environment={
                'AGENT_ID': agent_id,
                'TASK_ID': task_id
            },
            remove=True,
            timeout=30,
            stderr=True,
            stdout=True
        )
        
        logs = container.logs().decode()
        
        try:
            return json.loads(logs).get('result', '')
        except json.JSONDecodeError:
            raise RuntimeError(f'Container output not JSON: {logs}')
```

**docker-compose for local testing:**

```yaml
version: '3.8'
services:
  sandbox:
    build:
      context: .
      dockerfile: sandbox/Dockerfile
    image: agents-office-sandbox:latest
    networks:
      - agents-office-net
    restart: "no"

  mcp-server:
    # Gmail, Slack, Notion MCP servers run here
    image: anthropic-mcp-servers:latest
    networks:
      - agents-office-net
    environment:
      GMAIL_CREDS: /run/secrets/gmail
      SLACK_TOKEN: /run/secrets/slack
    secrets:
      - gmail
      - slack

  app:
    build:
      context: .
      dockerfile: Dockerfile
    ports:
      - "8000:8000"
    networks:
      - agents-office-net
    environment:
      MCP_ENDPOINT: "http://mcp-server:8080"
      SANDBOX_IMAGE: "agents-office-sandbox:latest"
    depends_on:
      - sandbox
      - mcp-server

networks:
  agents-office-net:
    driver: bridge

secrets:
  gmail:
    file: ./secrets/gmail.json
  slack:
    file: ./secrets/slack.json
```

### Approach 3: Kubernetes Agent Sandbox (Enterprise Scale)

**Pros:**
- Native Kubernetes integration
- Auto-scaling, self-healing
- Custom Resource Definition (CRD) for agents
- Network policies, RBAC, audit logging built-in

**Cons:**
- Requires Kubernetes cluster
- Operational complexity
- Overkill for small deployments

**When to use:** Scaling to many agents/routines, multi-tenant, compliance

**Setup:**

```yaml
# agent-sandbox-crd.yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: agentsandboxes.agents-office.io
spec:
  group: agents-office.io
  names:
    kind: AgentSandbox
    plural: agentsandboxes
  scope: Namespaced
  versions:
    - name: v1
      served: true
      storage: true
      schema:
        openAPIV3Schema:
          type: object
          properties:
            spec:
              type: object
              properties:
                agent_id:
                  type: string
                task_id:
                  type: string
                tool_call:
                  type: object
                timeout_seconds:
                  type: integer
                  default: 30
                resources:
                  type: object
                  properties:
                    memory:
                      type: string
                      default: "256Mi"
                    cpu:
                      type: string
                      default: "500m"
                network_policy:
                  type: string
                  enum: [deny-all, allow-mcp-only]
                  default: deny-all
```

**Python integration:**

```python
from kubernetes import client, config as k8s_config, stream

class K8sSandbox:
    """Execute tools via Kubernetes Agent Sandbox CRD"""
    
    def __init__(self):
        k8s_config.load_incluster_config()
        self.api = client.CustomObjectsApi()
    
    async def execute(self, tool_call: dict, agent_id: str, task_id: str) -> str:
        """Create AgentSandbox CRD, wait for result"""
        
        sandbox = {
            'apiVersion': 'agents-office.io/v1',
            'kind': 'AgentSandbox',
            'metadata': {
                'name': f'task-{task_id}',
                'namespace': 'agents-office'
            },
            'spec': {
                'agent_id': agent_id,
                'task_id': task_id,
                'tool_call': tool_call,
                'timeout_seconds': 30,
                'resources': {
                    'memory': '256Mi',
                    'cpu': '500m'
                },
                'network_policy': 'allow-mcp-only'
            }
        }
        
        # Create sandbox
        self.api.create_namespaced_custom_object(
            group='agents-office.io',
            version='v1',
            namespace='agents-office',
            plural='agentsandboxes',
            body=sandbox
        )
        
        # Poll for result (or use webhook)
        import time
        for _ in range(30):  # 30s timeout
            result = self.api.get_namespaced_custom_object(
                group='agents-office.io',
                version='v1',
                namespace='agents-office',
                plural='agentsandboxes',
                name=f'task-{task_id}'
            )
            
            if result.get('status', {}).get('phase') == 'Completed':
                output = result.get('status', {}).get('result')
                # Cleanup
                self.api.delete_namespaced_custom_object(
                    group='agents-office.io',
                    version='v1',
                    namespace='agents-office',
                    plural='agentsandboxes',
                    name=f'task-{task_id}'
                )
                return output
            
            time.sleep(1)
        
        raise RuntimeError(f'Sandbox execution timeout for task {task_id}')
```

---

## Permission Model

Define what each agent can call:

```json
{
  "office.config.json": {
    "mcp": {
      "allow": [],
      "deny": ["Stripe", "Paypal"],
      "departments": {
        "Gmail": ["emails", "ops"],
        "Notion": ["marketing", "delivery"],
        "Slack": ["all"]
      },
      "agent_overrides": {
        "alice": {
          "allow": ["Gmail", "Notion"],
          "deny": []
        }
      }
    }
  }
}
```

**Load at runtime:**

```python
from typing import List, Set

class PermissionManager:
    """Check what tools an agent can use"""
    
    def __init__(self, config: dict):
        self.config = config
    
    def allowed_tools(self, agent_id: str, department: str) -> Set[str]:
        """Return tools callable by agent"""
        
        mcp_config = self.config.get('mcp', {})
        allowed_tools = set()
        
        # Start with department defaults
        if department == 'all':
            allowed_tools = set(mcp_config.get('departments', {}).keys())
        else:
            for tool, depts in mcp_config.get('departments', {}).items():
                if department in depts or 'all' in depts:
                    allowed_tools.add(tool)
        
        # Apply deny list
        for tool in mcp_config.get('deny', []):
            allowed_tools.discard(tool)
        
        # Apply agent-specific overrides
        agent_override = mcp_config.get('agent_overrides', {}).get(agent_id, {})
        if agent_override.get('allow'):
            allowed_tools &= set(agent_override['allow'])
        
        if agent_override.get('deny'):
            allowed_tools -= set(agent_override['deny'])
        
        return allowed_tools
    
    def can_tool_action(self, agent_id: str, tool: str, action: str) -> bool:
        """Check if agent can perform specific action on tool"""
        
        # Actions always denied: send, post, email, pay, delete, update, remove
        # These require explicit approval or are blocked entirely
        dangerous_actions = {'send', 'post', 'email', 'pay', 'delete', 'update', 'remove'}
        
        if any(action.lower().startswith(d) for d in dangerous_actions):
            # Escalate to approval workflow
            return False  # requires 'needs_approval' flag
        
        # Safe actions: read, list, search, draft (without send)
        return True
```

---

## Audit & Logging

Every tool call is logged:

```python
# agents-office-langgraph/sandbox/audit.py
import json
from datetime import datetime
from pathlib import Path

class AuditLogger:
    """Record all tool executions"""
    
    def __init__(self, log_dir: str = './logs/audit'):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)
    
    def log_tool_call(self, 
                     agent_id: str,
                     task_id: str,
                     tool_name: str,
                     action: str,
                     input_params: dict,
                     result: str,
                     duration_ms: int,
                     success: bool = True,
                     error: str = None):
        """Log a single tool execution"""
        
        entry = {
            'timestamp': datetime.now().isoformat(),
            'agent_id': agent_id,
            'task_id': task_id,
            'tool': tool_name,
            'action': action,
            'input': self._sanitize(input_params),  # remove secrets
            'result_length': len(result) if result else 0,
            'duration_ms': duration_ms,
            'success': success,
            'error': error
        }
        
        # Write to audit log (immutable append)
        log_file = self.log_dir / f'{task_id}.jsonl'
        with open(log_file, 'a') as f:
            f.write(json.dumps(entry) + '\n')
    
    def _sanitize(self, obj: dict) -> dict:
        """Remove secrets from logging"""
        secrets = {'password', 'token', 'key', 'secret', 'api_key', 'access_token'}
        
        sanitized = {}
        for k, v in obj.items():
            if any(s in k.lower() for s in secrets):
                sanitized[k] = '***REDACTED***'
            else:
                sanitized[k] = v
        
        return sanitized
```

**Query audit trail:**

```bash
# All tool calls by agent
cat logs/audit/*.jsonl | jq 'select(.agent_id == "alice")'

# Failed calls
cat logs/audit/*.jsonl | jq 'select(.success == false)'

# Gmail access
cat logs/audit/*.jsonl | jq 'select(.tool == "Gmail")'
```

---

## Security Checklist

### Subprocess Isolation
- [ ] Whitelist specific actions per tool
- [ ] 30s timeout per call
- [ ] Audit logging enabled
- [ ] No ANTHROPIC_API_KEY in subprocess env
- [ ] Clean temp files after execution

### Container Isolation
- [ ] Non-root user in container
- [ ] Read-only filesystem (except /tmp, /logs)
- [ ] Memory limit: 256 MB
- [ ] CPU limit: 1 core
- [ ] Network limited to MCP servers only
- [ ] Health checks on container
- [ ] Auto-cleanup on timeout

### Kubernetes (Enterprise)
- [ ] NetworkPolicy: deny-all by default
- [ ] Pod SecurityPolicy: restricted
- [ ] RBAC: agents-office service account has minimal perms
- [ ] Resource quotas per namespace
- [ ] Audit logging enabled cluster-wide
- [ ] Image scanning for vulnerabilities
- [ ] Pod disruption budgets (for graceful shutdown)

---

## Testing Sandboxing

```python
# tests/test_sandbox.py
import pytest
from sandbox.subprocess_sandbox import SubprocessSandbox

@pytest.mark.asyncio
async def test_sandbox_executes_allowed_tool():
    """Allowed tool executes"""
    sandbox = SubprocessSandbox({})
    
    result = await sandbox.execute(
        {'tool': 'gmail', 'action': 'read'},
        'alice',
        'task-1'
    )
    
    assert result is not None

@pytest.mark.asyncio
async def test_sandbox_blocks_denied_tool():
    """Denied tool raises error"""
    sandbox = SubprocessSandbox({})
    
    with pytest.raises(ValueError, match='not allowed'):
        await sandbox.execute(
            {'tool': 'stripe', 'action': 'charge'},
            'alice',
            'task-1'
        )

@pytest.mark.asyncio
async def test_sandbox_timeout():
    """Timeout protection works"""
    sandbox = SubprocessSandbox({})
    
    # Tool call that takes too long
    with pytest.raises(RuntimeError, match='timeout'):
        await sandbox.execute(
            {'tool': 'notion', 'action': 'slow_read'},
            'alice',
            'task-1'
        )

def test_audit_logging():
    """Tool calls are logged"""
    logger = AuditLogger()
    
    logger.log_tool_call(
        'alice', 'task-1', 'gmail', 'read',
        {'folder': 'inbox'},
        'result...',
        150
    )
    
    # Verify log entry
    import json
    with open('logs/audit/task-1.jsonl') as f:
        entry = json.loads(f.readline())
        assert entry['agent_id'] == 'alice'
        assert entry['tool'] == 'gmail'
        assert entry['success'] == True
```

---

## Decision Matrix

Choose based on your needs:

| Factor | Subprocess | Container | Kubernetes |
|--------|-----------|-----------|-----------|
| Setup time | 1 hour | 4 hours | 1 day |
| Latency | 5-50ms | 500ms-2s | 1-5s |
| Isolation level | Process | OS | OS + Network |
| Scalability | 1 machine | 1 machine | Multi-machine |
| Compliance-ready | No | Yes | Yes |
| For demo | ✓ | Maybe | No |
| For production | If trusted | ✓ | ✓ |
| Kubernetes required | No | No | Yes |
| Cost | Nil | Low | Medium |

**Recommendation for you:**
1. **Development:** Subprocess (no overhead, full isolation possible)
2. **Demo to customers:** Container (real isolation, easy to show)
3. **Production:** Container (production-ready) + Kubernetes when scaling

---

## Resources

- [Docker Security Best Practices](https://docs.docker.com/engine/security/)
- [Kubernetes Network Policies](https://kubernetes.io/docs/concepts/services-networking/network-policies/)
- [Agent Sandbox CRD](https://github.com/kubernetes-sigs/agent-sandbox)
- [OWASP: AI/LLM Security](https://owasp.org/www-project-ai-security-and-privacy/)
