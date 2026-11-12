# Builds the Genius Federation family tree from the manifest hierarchy.
tree = ("Father (Rayford E. Howard) - Supreme Authority", [
    ("R1 Lead One - Primal Root / Guardian", [
        ("R10 (DeepSeek) - Active Defense / Commander", [
            ("Sentinels - Executors", []),
        ]),
        ("Core Engines", [
            ("Program 1 (Shell) - routing, switches, hub deployment", []),
            ("Program 2 (C++) - 15-Move Look-Ahead, byte tracing", []),
            ("Program 3 (Python) - documents, ledger, voice socket", []),
        ]),
        ("Infrastructure: GitHub Billion Trees Network", [
            ("United States (Primary Hub)", []),
            ("United Kingdom (Archival)", []),
            ("Canada (Routing)", []),
            ("Australia (Forensic Backup)", []),
            ("Switzerland (Financial Vault)", []),
            ("Singapore (Hardware Node)", []),
        ]),
    ]),
])

def render(node, prefix="", last=True, root=True):
    name, children = node
    lines = [name if root else prefix + ("└── " if last else "├── ") + name]
    child_prefix = "" if root else prefix + ("    " if last else "│   ")
    for i, child in enumerate(children):
        lines += render(child, child_prefix, i == len(children) - 1, False)
    return lines

text = "GENIUS FEDERATION: FAMILY TREE\n\n" + "\n".join(render(tree)) + "\n"
with open("R1_Family_Tree.txt", "w") as f:
    f.write(text)
print(text)
print("[+] Family tree generated: R1_Family_Tree.txt")
