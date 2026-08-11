import csv
import os
import datetime
# Název vstupního souboru
input_file = "data3.csv"

# Výstupní složka
output_dir = "actions3"
os.makedirs(output_dir, exist_ok=True)

with open(input_file, newline="", encoding="utf-8") as csvfile:
    reader = list(csv.reader(csvfile))
    header = reader[1]  # hlavičky
    data = reader[2:]   # data

    # Vynecháme řádky, které nejsou data (např. řádek s "100 pts")
    data = [row for row in data if not any("pts" in cell for cell in row)]

    # Najdeme index, kde začínají názvy akcí
    try:
        start_index = None
        for i, col in enumerate(header):
            if "Nahá Míle" in col:
                start_index = i
                break
        if start_index is None:
            raise ValueError("Začátek akcí nebyl nalezen.")
    except ValueError as e:
        print(e)
        exit()

    # Pro každý sloupec s akcí
    for col_index in range(start_index, len(header)):
        action_name = header[col_index].strip().replace('"', '').replace("/", "_").replace("\n", "_").replace(" ", "_")
        output_path = os.path.join(output_dir, f"{action_name}.csv")

        with open(output_path, "w", newline="", encoding="utf-8") as outfile:
            writer = csv.writer(outfile)

            # Hlavička souboru
            writer.writerow(["Časová_známka", "Telefon", "Jméno", "Body"])

            for row in data:
                telefon = row[0].strip()
                jmeno = row[1].strip()
                body = row[col_index].strip() if col_index < len(row) else ""
                telefon = telefon .rstrip("\u202c")

                if body != "" and telefon != "":  # pouze pokud je záznam
                    writer.writerow([datetime.datetime.now(), telefon, jmeno, body])

print("✅ Hotovo — akce CSV byly vytvořeny ve složce 'actions' s časovou značkou.")
