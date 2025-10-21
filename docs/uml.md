# UML Diagrams

These diagrams are generated from the Python sources under `src/` using Pyreverse (from Pylint). The generator script is [`scripts/generate_uml.py`](https://github.com/rwydaegh/goliat/blob/master/scripts/generate_uml.py).

- Class diagram (PlantUML): [classes.puml](classes.puml)
- Packages diagram (PlantUML): [packages_GOLIAT.puml](packages_GOLIAT.puml)

How to view
- Use any PlantUML viewer (e.g., VS Code PlantUML extension, IntelliJ PlantUML plugin, or https://www.plantuml.com/plantuml).
- Alternatively, use a browser-based renderer such as Kroki (https://kroki.io) by uploading the .puml file.

How to regenerate
- Ensure the Sim4Life Python (with pip) is on PATH as described in the README.
- Then run:
  - Windows (with Sim4Life Python): 
    - "D:\Program Files\Sim4Life_8.2.0.18061\Python\python.exe" scripts/generate_uml.py
  - Or from a shell session where `python` resolves to the Sim4Life Python:
    - source .bashrc && python scripts/generate_uml.py

Notes
- The generated PlantUML files are committed to docs/ so they can be downloaded and rendered externally without requiring additional MkDocs plugins.
- If you want inline rendering inside MkDocs, add a PlantUML-capable Markdown extension or serve via Kroki. For example, the mkdocs-kroki plugin can render `@startuml ... @enduml` fences at build time.