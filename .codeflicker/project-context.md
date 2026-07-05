# Project Context and Deployment Configuration

## Deployment Environment

**IMPORTANT**: This project's client and server are **NOT deployed locally on Windows**. They are deployed to **remote servers via SSH**.

### Key Points

- ✅ Code is executed on **remote Linux servers**
- ✅ Use SSH for deployment and command execution
- ❌ Do NOT run `docker-compose` or `npm` commands locally on Windows
- ❌ Do NOT assume localhost deployment

### Execution Strategy

When working with this project:

1. **Container Management**: All Docker commands must be executed via SSH on the remote server
2. **Build & Deploy**: Use the deployment scripts designed for remote execution
3. **Debugging**: Remote debugging requires SSH port forwarding
4. **File Changes**: Code changes need to be synced to remote before taking effect

### Remote Access

- Server connection method: SSH
- Client deployment location: Remote server
- Server deployment location: Remote server

---

*This file helps AI assistants understand the project's deployment architecture and avoid incorrect local execution assumptions.*
