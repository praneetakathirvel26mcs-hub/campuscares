"""Generate 400 labelled synthetic campus complaints for model training/testing."""
import csv
import random
from pathlib import Path

random.seed(42)
OUT = Path(__file__).with_name("synthetic_complaints.csv")

examples = {
    "IT": {
        "subjects": ["campus Wi-Fi not working", "computer lab systems are slow", "projector has no signal", "college portal login fails", "printer is offline", "network connection keeps disconnecting", "software is not opening", "student portal shows an error", "computer cannot connect to internet", "smart board display is not working"],
        "details": ["The internet connection drops during class", "Several students cannot access the online portal", "The system displays an error message", "This issue affects our lab session", "Restarting the device did not fix the problem", "The network is unavailable in this room", "The computer equipment needs technical support", "The issue started this morning", "We cannot complete our online work", "Please check the network and computer system"],
        "locations": ["computer lab", "library", "seminar hall", "classroom", "admin block", "campus network"]
    },
    "Electrical": {
        "subjects": ["classroom lights are not working", "ceiling fan has stopped", "power socket is damaged", "frequent power cuts in lab", "tube light keeps flickering", "electrical switch is sparking", "corridor lights are off", "projector power supply is failing", "exposed electrical wire near desk", "laboratory power outlet is dead"],
        "details": ["The room becomes difficult to use during class", "The electrical fitting needs inspection", "There is no power at the outlet", "The issue has continued since yesterday", "Please send an electrician to inspect it", "The light flickers repeatedly", "The fan stopped working suddenly", "This may be unsafe for students", "The switchboard is not operating properly", "Power supply is interrupting our practical session"],
        "locations": ["classroom", "physics lab", "corridor", "library", "hostel block", "lecture hall"]
    },
    "Maintenance": {
        "subjects": ["broken classroom desk", "door handle is loose", "roof is leaking", "window glass is broken", "classroom chair is damaged", "water tap is leaking", "floor tiles are broken", "ceiling plaster is falling", "laboratory table needs repair", "classroom lock is jammed"],
        "details": ["The furniture needs repair", "Water enters the room during rain", "The damaged part may cause an injury", "This has been reported previously", "Please arrange maintenance staff", "The door cannot close properly", "The floor is uneven near the entrance", "The fixture has become loose", "The classroom needs repair work", "The issue affects normal classroom use"],
        "locations": ["classroom", "main building", "laboratory", "library", "entrance", "lecture block"]
    },
    "Sanitation": {
        "subjects": ["washroom needs cleaning", "dustbins are overflowing", "bad smell near restroom", "garbage has not been collected", "washbasin is unhygienic", "drain is blocked", "campus area has litter", "restroom supplies are missing", "dirty water near washroom", "sanitation issue in common area"],
        "details": ["The area needs immediate cleaning", "Waste has been left here since yesterday", "The smell is affecting nearby classrooms", "Please arrange cleaning staff", "The drain is not allowing water to flow", "The dustbin is full and waste is scattered", "The wash area is not hygienic", "This issue is affecting students", "Please inspect the sanitation facilities", "Regular cleaning appears to have been missed"],
        "locations": ["washroom", "canteen", "corridor", "campus garden", "common area", "hostel washroom"]
    }
}

rows = []
for category, data in examples.items():
    for i in range(100):
        title = random.choice(data["subjects"])
        detail = random.choice(data["details"])
        location = random.choice(data["locations"])
        text = f"{title}. {detail}. Location: {location}."
        rows.append({"text": text, "category": category, "title": title, "description": detail, "location": location})
random.shuffle(rows)
with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["text", "category", "title", "description", "location"])
    writer.writeheader()
    writer.writerows(rows)
print(f"Created {len(rows)} labelled synthetic complaints at {OUT}")
