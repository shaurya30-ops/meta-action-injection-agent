import re


def render_template(template: str, context: dict) -> str:
    """
    Simple template renderer supporting:
    - {{variable}} substitution
    - {% if variable %}...{% else %}...{% endif %} conditionals
    """
    # Handle {% if %}...{% else %}...{% endif %}
    if_pattern = re.compile(
        r"\{%\s*if\s+(\w+)\s*%\}(.*?)(?:\{%\s*else\s*%\}(.*?))?\{%\s*endif\s*%\}",
        re.DOTALL,
    )

    def replace_if(match):
        var_name = match.group(1)
        true_block = match.group(2)
        false_block = match.group(3) or ""
        value = context.get(var_name, "")
        # Truthy check: non-empty string, non-zero number, True bool
        if value and value != "0" and value is not False:
            return true_block
        return false_block

    result = if_pattern.sub(replace_if, template)

    # Handle == comparison: {% if variable == 'value' %}
    eq_pattern = re.compile(
        r"\{%\s*if\s+(\w+)\s*==\s*['\"]([^'\"]*?)['\"]\s*%\}(.*?)(?:\{%\s*else\s*%\}(.*?))?\{%\s*endif\s*%\}",
        re.DOTALL,
    )

    def replace_eq(match):
        var_name = match.group(1)
        compare_value = match.group(2)
        true_block = match.group(3)
        false_block = match.group(4) or ""
        actual_value = str(context.get(var_name, ""))
        if actual_value == compare_value:
            return true_block
        return false_block

    result = eq_pattern.sub(replace_eq, result)

    # Handle {{variable}} substitution
    var_pattern = re.compile(r"\{\{(\w+)\}\}")

    def replace_var(match):
        var_name = match.group(1)
        return str(context.get(var_name, ""))

    result = var_pattern.sub(replace_var, result)

    return result.strip()
