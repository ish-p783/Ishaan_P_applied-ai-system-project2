# PawPal+ Care Guidelines (RAG knowledge base)

This file is the knowledge base the AI assistant retrieves from before it
answers. Each entry is a short, factual snippet with a `Tags:` line. When you
chat with a pet selected, `ai_assistant.retrieve_guidelines()` scans these
entries and pulls the ones whose tags match the pet's species, breed, or
health conditions. Those matched snippets get pasted into the prompt, so the
AI's advice is grounded in this file instead of made up.

**How to extend it:** copy an entry, edit the `Tags:` line (lowercase, comma-
separated), and write 1-3 factual sentences. Keep entries short — retrieval
works better on many small entries than a few long ones.

---

### Daily exercise for high-energy dogs
Tags: dog, labrador, husky, border collie, retriever, hyper, high-energy
High-energy dogs generally need 60-90 minutes of active exercise per day, split
across two or more sessions. Under-exercised high-energy dogs often develop
destructive or restless behaviour, so more frequent walks and off-leash play
(a park, a long fetch session) help more than one short walk.

### Exercise for low-energy or senior dogs
Tags: dog, senior, older, bulldog, pug, low-energy, arthritis
Older or low-energy dogs do better with shorter, gentler walks (15-25 minutes)
and rest between them. Avoid long or high-intensity sessions, especially in
heat, for flat-faced (brachycephalic) breeds like pugs and bulldogs.

### General cat activity needs
Tags: cat, indoor, play, hyper
Indoor cats need short bursts of active play (2-3 sessions of 10-15 minutes)
to stay healthy and avoid boredom. Interactive toys (feather wands, laser
pointers) mimic hunting and are better than leaving toys out all day.

### Feeding frequency — dogs
Tags: dog, feeding, food, meals
Most adult dogs do well on two measured meals a day, morning and evening.
Puppies under six months usually need three to four smaller meals. Keep meal
times consistent day to day.

### Feeding frequency — cats
Tags: cat, feeding, food, meals
Adult cats are usually fed two measured meals a day, though some do better with
several small portions. Keep fresh water available at all times.

### Medication timing
Tags: medication, meds, medicine, health, pill
Give medications at the same time each day to keep levels steady. Some meds
must be given with food and others on an empty stomach — follow the vet's label
exactly. Never double a dose to make up for a missed one without asking a vet.

### Weight management
Tags: dog, cat, overweight, weight, obese, diet
For an overweight pet, increase gentle activity gradually and measure food
portions rather than free-feeding. Sudden intense exercise can injure an
out-of-shape pet, so ramp up slowly.

### Grooming basics
Tags: dog, cat, grooming, brushing, coat, long-haired
Long-haired breeds need brushing several times a week to prevent mats; short-
haired pets need it less often. Regular brushing also lets you spot skin issues
early.

### When a pet seems unwell
Tags: sick, unwell, ill, vomiting, lethargy, not eating, health
Loss of appetite, lethargy, vomiting, or diarrhoea lasting more than a day
warrants a vet call. This assistant can suggest gentle adjustments (lighter
meals, more rest, more frequent short walks) but is not a substitute for a
veterinarian — always recommend a vet for anything serious or persistent.

### Puppy and kitten needs
Tags: puppy, kitten, young, dog, cat
Young animals need more frequent meals, shorter but more frequent activity, and
consistent socialisation and training sessions. Keep training sessions short
(5-10 minutes) and positive.
