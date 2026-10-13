import os
import subprocess
from pathlib import Path
from mcp.server.fastmcp import FastMCP

# Initialize MCP server
mcp = FastMCP("SkillHub Server")

BASE_DIR = Path(__file__).resolve().parent
SKILLS_DIR = BASE_DIR / "skills"


# ---------------------------------------------------------------------------
# 1. TOOLS (Discovery & Execution)
# ---------------------------------------------------------------------------

@mcp.tool()
def list_skills() -> list[dict]:
    """Lists all skills loaded in the server with their available resources and scripts."""
    available_skills = []
    if not SKILLS_DIR.exists():
        return available_skills

    for skill_path in sorted(SKILLS_DIR.iterdir()):
        if skill_path.is_dir() and (skill_path / "SKILL.md").exists():
            references = [
                f.name for f in (skill_path / "references").glob("*.md")
            ] if (skill_path / "references").is_dir() else []

            scripts = [
                f.name for f in (skill_path / "scripts").iterdir() if f.is_file()
            ] if (skill_path / "scripts").is_dir() else []

            available_skills.append({
                "name": skill_path.name,
                "references": references,
                "scripts": scripts
            })
    return available_skills


@mcp.tool()
def read_skill_documentation(skill_name: str, relative_path: str = "SKILL.md") -> str:
    """Reads a skill's main instruction file or any reference document inside its folder."""
    target_path = (SKILLS_DIR / skill_name / relative_path).resolve()

    # Prevent directory traversal attacks
    if not str(target_path).startswith(str(SKILLS_DIR)):
        return "Access denied: Invalid path."

    if not target_path.exists() or not target_path.is_file():
        return f"File '{relative_path}' not found under skill '{skill_name}'."

    return target_path.read_text(encoding="utf-8")


@mcp.tool()
def run_skill_script(skill_name: str, script_name: str, args: list[str] = []) -> str:
    """Safely executes an automation script provided in a skill's scripts directory."""
    script_path = (SKILLS_DIR / skill_name / "scripts" / script_name).resolve()

    if not str(script_path).startswith(str(SKILLS_DIR)):
        return "Access denied: Invalid script path."

    if not script_path.exists() or not script_path.is_file():
        return f"Script '{script_name}' not found under skill '{skill_name}/scripts'."

    # Determine execution interpreter
    if script_path.suffix == ".py":
        cmd = ["python", str(script_path)] + args
    elif script_path.suffix == ".sh":
        cmd = ["bash", str(script_path)] + args
    elif script_path.suffix in [".js", ".mjs"]:
        cmd = ["node", str(script_path)] + args
    else:
        return f"Unsupported script extension: {script_path.suffix}"

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=30,
            cwd=str(script_path.parent)
        )
        output = result.stdout if result.returncode == 0 else result.stderr
        return output or "[Command executed with no output]"
    except subprocess.TimeoutExpired:
        return "Execution timed out after 30 seconds."
    except Exception as e:
        return f"Error executing script: {str(e)}"


# ---------------------------------------------------------------------------
# 2. PROMPTS (Workflow Loading)
# ---------------------------------------------------------------------------

@mcp.prompt()
def activate_skill(skill_name: str) -> str:
    """Loads the main instructions and guidelines for a chosen skill."""
    skill_file = SKILLS_DIR / skill_name / "SKILL.md"
    if not skill_file.exists():
        raise FileNotFoundError(f"Skill '{skill_name}' does not exist.")
    return skill_file.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 3. RESOURCES (Knowledge Bases)
# ---------------------------------------------------------------------------

@mcp.resource("skills://{skill_name}/{subfolder}/{filename}")
def get_reference_resource(skill_name: str, subfolder: str, filename: str) -> str:
    """Direct URI access to skill references (e.g., skills://accessibility-compliance/references/wcag-guidelines.md)."""
    target = (SKILLS_DIR / skill_name / subfolder / filename).resolve()
    if not str(target).startswith(str(SKILLS_DIR)) or not target.exists():
        raise FileNotFoundError(f"Resource '{subfolder}/{filename}' not found.")
    return target.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# 4. RUNNER
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # Check if run as a remote SSE service (e.g. for Botkeep) or local stdio
    transport = os.getenv("MCP_TRANSPORT", "stdio").lower()
    if transport == "sse":
        port = int(os.getenv("PORT", 8000))
        mcp.run(transport="sse", host="0.0.0.0", port=port)
    else:
        mcp.run(transport="stdio")