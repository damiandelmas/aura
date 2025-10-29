"""
Jinja2 templates for structured output
"""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader

# Template directory
TEMPLATE_DIR = Path(__file__).parent

# Create Jinja2 environment
env = Environment(
    loader=FileSystemLoader(str(TEMPLATE_DIR)),
    trim_blocks=True,
    lstrip_blocks=True
)


def render(results, template_name):
    """Render results with specified template"""
    template = env.get_template(f"{template_name}.j2")
    return template.render(results=results)
