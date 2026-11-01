from pathlib import Path

folder = Path(__file__).resolve().parent

print("Database files found:\n")

for file in folder.glob("*.db"):
    print(f"File: {file.name}")
    print(f"Size: {file.stat().st_size} bytes")
    print("-" * 30)