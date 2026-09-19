import hashlib, subprocess, pathlib
REV  = "9c4ae87d1bd493a31508ffbfc90959f7d468e4ab"
PATH = "eval/questions_vnext_regression.yaml"
OUT  = pathlib.Path("eval/questions_sections_after.yaml")
TARGET = "85bd4381cc6004dd763c43fa904bc6638c3e2e2c1862783f47833302861b9882"

blob = subprocess.run(["git","cat-file","blob",f"{REV}:{PATH}"],
                      capture_output=True).stdout
data = blob.replace(b"\r\n", b"\n").replace(b"\n", b"\r\n")
h = hashlib.sha256(data).hexdigest()
print("hash obtenido :", h)
print("hash esperado :", TARGET)
if h != TARGET:
    print("\nNO coincide. No se escribe nada.")
    raise SystemExit(1)
if OUT.exists():
    print(f"\n{OUT} ya existe. No se sobrescribe.")
    raise SystemExit(1)
OUT.write_bytes(data)
print(f"\nEscrito {OUT} ({len(data)} bytes)")
