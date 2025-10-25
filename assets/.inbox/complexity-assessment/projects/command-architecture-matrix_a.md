# Slash Command Complexity Framework

## 🚀 Lean (Minimal Viable)
**Use for:**  
- Quick, one-off commands  
- Simple team workflows  
- Rapid prototyping  
- Individual developer needs  

**Features:**  
- Single template, minimal complexity  
- 1–20 lines  
- No YAML unless essential  
- Direct `$ARGUMENTS` usage  
- Copy proven examples  

**Example:** `clean.md`, `fix-issue.md`

---

## ⚖️ Moderate (Structured)
**Use for:**  
- Team standardization  
- Multi-step workflows  
- Some customization  
- Growing command library  

**Features:**  
- Multiple templates (3–5 types)  
- 20–50 lines  
- Basic YAML frontmatter  
- Argument parsing logic  
- Template selection system  

**Example:** Smart template selection by complexity

---

## 🏗️ Complex (Enterprise)
**Use for:**  
- Large organizations  
- Compliance needs  
- Advanced automation  
- Integration with multiple systems  

**Features:**  
- Full workflow orchestration  
- 50+ lines, multiple sections  
- Rich YAML metadata  
- Hook integration  
- Multi-agent coordination  

**Example:** Full CI/CD pipeline commands

---

## 🧩 Modular (Component-Based)
**Use for:**  
- High reusability  
- Multiple command families  
- Template sharing  
- Evolving requirements  

**Features:**  
- Import/include system (`@templates`)  
- Shared component library  
- Dynamic assembly  
- Version management  
- Composition over creation  

**Example:** `@templates/security.md` + `@templates/testing.md`

---

## Decision Matrix

| Factor          | Lean    | Moderate | Complex | Modular                      |
|-----------------|---------|----------|---------|------------------------------|
| Time to create  | Minutes | Hours    | Days    | Initial: Days, Then: Minutes |
| Maintenance     | Low     | Medium   | High    | Medium                       |
| Team size       | 1–3     | 3–10     | 10+     | Any                          |
| Reusability     | Low     | Medium   | Low     | High                         |
| Standardization | Minimal | Good     | Rigid   | Flexible                     |
| Learning curve  | None    | Low      | High    | Medium                       |

---

## Progression Path

Lean → Moderate → **Complex** _or_ **Modular**  

  Recommendation: Start lean, evolve to moderate, then choose complex OR modular based on
  your scaling needs.
