students = [
    {"name": "Hermione", "house": "Gryffindor", "patrnous": "Otter" },
    {"name": "Harry", "house": "Gryffindor", "patrnous": "Stag"},
    {"name": "Ron", "house": "Gryffindor", "patrnous": "Jack Russel Terrior"},
    { "name": "Draco", "house": "Slytherin", "patrnous": None}
]

for student in students:
    print(student["name"], student["house"], student["patrnous"], sep=", ")


