import hashlib, subprocess
PATH = "eval/questions_vnext_regression.yaml"
TARGET = "85bd4381cc6004dd763c43fa904bc6638c3e2e2c1862783f47833302861b9882"
revs = subprocess.run(["git","rev-list","--all","--",PATH],
                      capture_output=True, text=True).stdout.split()
seen = {}
for rev in revs:
    blob = subprocess.run(["git","cat-file","blob",f"{rev}:{PATH}"],
                          capture_output=True).stdout
    if not blob:
        continue
    lf = blob.replace(b"\r\n", b"\n")
    crlf = lf.replace(b"\n", b"\r\n")
    for form, data in (("LF", lf), ("CRLF", crlf)):
        h = hashlib.sha256(data).hexdigest()
        seen.setdefault(h, (rev, form))
print(f"{len(revs)} revisiones, {len(seen)} hashes\n")
hit = None
for h, (rev, form) in seen.items():
    if h == TARGET:
        hit = (rev, form)
    mark = "<-- ES ESTE  " if h == TARGET else "             "
    print(mark + h[:16] + "  " + rev[:9] + "  " + form)
if hit:
    print(f"\nEncontrado en {hit[0]} como {hit[1]}")
    print(f"git show {hit[0]}:{PATH} > eval/questions_sections_after.yaml")
else:
    print("\nNo esta en git en ninguna de las dos formas.")
