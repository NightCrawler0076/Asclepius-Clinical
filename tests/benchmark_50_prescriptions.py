"""
Evaluation Suite: 50 Diverse Clinical Prescriptions
Tests Qwen2.5 1.5B Instruct GGUF on extraction accuracy across specialties.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from clinical.llm_refiner import load_model, is_available, refine as llm_refine
from clinical.extractor import extract
from clinical.normalizer import normalize_entities

# 50 comprehensive clinical cases spanning specialties:
# General Practice, Pulmonology, Cardiology, Endocrinology, Gastroenterology,
# Pediatrics, Dermatology, ENT, Orthopedics, Neurology, Psychiatry, Urology, Gynecology
BENCHMARK_CASES = [
    # ── Acute Respiratory & ENT (1-5) ──
    {
        "id": "case_01",
        "category": "ENT / Respiratory",
        "transcript": "Patient with sore throat, runny nose and fever for 2 days. Acute pharyngitis. Start Augmentin 625mg BD for 5 days, Paracetamol 650mg TDS for 3 days, and Cetirizine 10mg OD at night for 5 days. Gargle with warm saline. Review after 5 days.",
        "expected_meds": ["Augmentin", "Paracetamol", "Cetirizine"],
        "expected_diag": ["pharyngitis"],
    },
    {
        "id": "case_02",
        "category": "ENT / Respiratory",
        "transcript": "Complaining of severe ear pain and yellowish discharge from right ear. Acute otitis media. Prescribe Amoxicillin 500mg TDS for 7 days, Meftal-Spas SOS for pain, and Ciplox ear drops 3 drops three times daily. Keep ear dry. Follow up in 1 week.",
        "expected_meds": ["Amoxicillin", "Meftal", "Ciplox"],
        "expected_diag": ["otitis media"],
    },
    {
        "id": "case_03",
        "category": "Pulmonology",
        "transcript": "Chronic dry cough with wheezing and nocturnal dyspnea. Bronchial asthma exacerbation. Prescribe Foracort 200 inhaler 2 puffs BD, Montek-LC one tablet at bedtime for 14 days, and Deriphyllin 150mg BD for 5 days. Chest X-ray and Spirometry. Avoid cold drinks. Review in 2 weeks.",
        "expected_meds": ["Foracort", "Montek-LC", "Deriphyllin"],
        "expected_diag": ["asthma"],
    },
    {
        "id": "case_04",
        "category": "Pulmonology",
        "transcript": "High fever with chills, productive cough with rusty sputum. Right lower lobe pneumonia. Start Azithromycin 500mg once daily for 5 days, Cefuroxime 500mg twice daily for 7 days, and Dolo 650mg SOS. Sputum culture and CBC. Steam inhalation thrice daily. Follow up in 3 days.",
        "expected_meds": ["Azithromycin", "Cefuroxime", "Dolo"],
        "expected_diag": ["pneumonia"],
    },
    {
        "id": "case_05",
        "category": "ENT / Allergy",
        "transcript": "Sneezing bursts, watery eyes, nasal blockage every morning. Allergic rhinitis. Give Allegra 120mg OD in morning, Flomist nasal spray 1 spray each nostril daily for 1 month, and Montair 10mg HS. Avoid dust and pollen. Review after 1 month.",
        "expected_meds": ["Allegra", "Flomist", "Montair"],
        "expected_diag": ["allergic rhinitis"],
    },

    # ── Gastroenterology (6-10) ──
    {
        "id": "case_06",
        "category": "Gastroenterology",
        "transcript": "Complaints of retrosternal burning and acid regurgitation after meals. GERD. Start Pan-D one capsule OD before breakfast for 14 days, Gelusil liquid 2 teaspoons after meals TDS, and Ganaton 50mg TDS before food. Avoid spicy food and lying down immediately after meals. Review after 2 weeks.",
        "expected_meds": ["Pan-D", "Gelusil", "Ganaton"],
        "expected_diag": ["GERD"],
    },
    {
        "id": "case_07",
        "category": "Gastroenterology",
        "transcript": "Watery loose stools 6 episodes since yesterday with abdominal cramping and nausea. Acute gastroenteritis. Give Oflox-OZ one tablet BD for 5 days, Econorm sachet twice daily for 3 days, and ORS Electral 1 liter sipped throughout the day. Stool routine examination. Drink boiled cooled water.",
        "expected_meds": ["Oflox-OZ", "Econorm", "ORS"],
        "expected_diag": ["gastroenteritis"],
    },
    {
        "id": "case_08",
        "category": "Gastroenterology",
        "transcript": "Upper abdominal pain, epigastric tenderness, bloating. Peptic ulcer disease. Give Rabeprazole 20mg BD before food for 4 weeks, Sucralfate suspension 10ml TDS 1 hour before meals for 2 weeks. Upper GI Endoscopy. Stop NSAIDs and smoking. Review in 1 month.",
        "expected_meds": ["Rabeprazole", "Sucralfate"],
        "expected_diag": ["ulcer"],
    },
    {
        "id": "case_09",
        "category": "Gastroenterology",
        "transcript": "Severe spasmodic lower abdominal pain and vomiting. Colicky pain. Give Drotin-M one tablet stat then SOS, Emset 4mg stat and TDS as needed. Ultrasound abdomen and pelvis. Urgent surgical review if pain radiates to right iliac fossa.",
        "expected_meds": ["Drotin-M", "Emset"],
        "expected_diag": ["pain"],
    },
    {
        "id": "case_10",
        "category": "Gastroenterology",
        "transcript": "Constipation for 4 days, hard stools, straining. Give Cremaffin Plus syrup 15ml at bedtime for 5 days and Isabgol husk 2 spoons in warm water at night. High fiber diet and drink 3 liters of water daily.",
        "expected_meds": ["Cremaffin", "Isabgol"],
        "expected_diag": ["constipation"],
    },

    # ── Cardiology & Hypertension (11-15) ──
    {
        "id": "case_11",
        "category": "Cardiology",
        "transcript": "Known hypertensive. BP recorded today is 156/96. Essential hypertension uncontrolled. Prescribe Telma-H 40 once daily in morning, Amlodipine 5mg OD, and continue Ecosprin 75mg after lunch. ECG, Lipid profile and Serum Creatinine. Salt restriction. Review after 2 weeks.",
        "expected_meds": ["Telma", "Amlodipine", "Ecosprin"],
        "expected_diag": ["hypertension"],
    },
    {
        "id": "case_12",
        "category": "Cardiology",
        "transcript": "Exertional retrosternal heaviness and palpitations. Stable angina with ischemic heart disease. Prescribe Sorbitrate 5mg sublingually SOS for chest pain, Metoprolol 50mg OD morning, and Atorva 40mg at bedtime. TMT and 2D Echo. Strict lifestyle modification. Review in 10 days.",
        "expected_meds": ["Sorbitrate", "Metoprolol", "Atorva"],
        "expected_diag": ["angina", "ischemic heart disease"],
    },
    {
        "id": "case_13",
        "category": "Cardiology",
        "transcript": "Breathlessness on exertion and bilateral pedal edema. Congestive heart failure. Start Lasix 40mg once daily in morning, Aldactone 25mg OD, and Ramipril 2.5mg OD. Daily weight monitoring, fluid limit to 1.5 liters daily. Serum electrolytes and KFT. Follow up in 1 week.",
        "expected_meds": ["Lasix", "Aldactone", "Ramipril"],
        "expected_diag": ["heart failure"],
    },
    {
        "id": "case_14",
        "category": "Cardiology",
        "transcript": "Irregular pulse and palpitations. Atrial fibrillation. Prescribe Cardarone 100mg once daily, Eliquis 5mg BD, and Concor 2.5mg OD. Holter monitoring 24 hours. INR monitoring not required for Eliquis. Emergency room if sudden weakness or speech slurring.",
        "expected_meds": ["Cardarone", "Eliquis", "Concor"],
        "expected_diag": ["atrial fibrillation"],
    },
    {
        "id": "case_15",
        "category": "Cardiology",
        "transcript": "Hypercholesterolemia discovered on routine checkup. LDL is 170. Dyslipidemia. Prescribe Rosuvas 10mg once daily at night for 3 months, and CoQ10 100mg daily. Repeat lipid profile after 12 weeks. Low fat diet and regular exercise.",
        "expected_meds": ["Rosuvas", "CoQ10"],
        "expected_diag": ["dyslipidemia"],
    },

    # ── Endocrinology & Diabetes (16-20) ──
    {
        "id": "case_16",
        "category": "Endocrinology",
        "transcript": "Known Type 2 Diabetes with high fasting sugars. HbA1c is 8.8%. Start Glycomet-GP 1 one tablet before breakfast, Januvia 100mg once daily, and continue Voglibose 0.2mg with meals TDS. Fasting and PP blood sugars weekly log. Diabetic diet and foot care. Follow up in 1 month.",
        "expected_meds": ["Glycomet", "Januvia", "Voglibose"],
        "expected_diag": ["diabetes"],
    },
    {
        "id": "case_17",
        "category": "Endocrinology",
        "transcript": "Patient with fatigue, hair loss and weight gain. TSH is elevated at 9.4. Primary hypothyroidism. Prescribe Thyronorm 50mcg once daily on empty stomach 1 hour before tea or breakfast. Repeat TSH after 6 weeks. Do not take calcium tablets with Thyronorm.",
        "expected_meds": ["Thyronorm"],
        "expected_diag": ["hypothyroidism"],
    },
    {
        "id": "case_18",
        "category": "Endocrinology",
        "transcript": "Severe burning and tingling sensation in both soles. Diabetic peripheral neuropathy. Start Pregabalin 75mg at night, Methylcobalamin 1500mcg OD for 1 month, and continue Metformin 1000mg BD. Nerve conduction study. Inspect feet daily for cuts.",
        "expected_meds": ["Pregabalin", "Methylcobalamin", "Metformin"],
        "expected_diag": ["neuropathy", "diabetes"],
    },
    {
        "id": "case_19",
        "category": "Endocrinology",
        "transcript": "Uncontrolled diabetes with proteinuria. Diabetic nephropathy. Start Forxiga 10mg once daily in morning, Telmisartan 40mg OD, and Linagliptin 5mg OD. Spot urine albumin creatinine ratio and KFT. Stay well hydrated. Review in 4 weeks.",
        "expected_meds": ["Forxiga", "Telmisartan", "Linagliptin"],
        "expected_diag": ["diabetic nephropathy"],
    },
    {
        "id": "case_20",
        "category": "Endocrinology",
        "transcript": "Postmenopausal lady with severe back pain and low bone density. Osteoporosis. Prescribe Shelcal-HD 1 tablet daily after food for 3 months, Arachitol 60K nano shots once weekly for 8 weeks, and Gemcal. DEXA scan. Sun exposure 20 minutes daily. Review in 2 months.",
        "expected_meds": ["Shelcal", "Arachitol"],
        "expected_diag": ["osteoporosis"],
    },

    # ── Infectious Diseases & Tropical Fevers (21-25) ──
    {
        "id": "case_21",
        "category": "Infectious Disease",
        "transcript": "High continuous fever with step-ladder pattern, coated tongue and abdominal pain for 6 days. Typhoid fever suspected. Give Cefixime 200mg BD for 10 days, Azithromycin 500mg OD for 7 days, and Paracetamol 650mg TDS SOS. Widal test and Blood Culture. Drink boiled water.",
        "expected_meds": ["Cefixime", "Azithromycin", "Paracetamol"],
        "expected_diag": ["typhoid"],
    },
    {
        "id": "case_22",
        "category": "Infectious Disease",
        "transcript": "Sudden onset high fever with severe retro-orbital headache, body ache and rash. Dengue fever NS1 positive. Give Dolo 650mg every 6 hours SOS. Strictly avoid aspirin and ibuprofen. Platelet count and hematocrit daily. Drink ORS, tender coconut water and papaya leaf extract. Hospitalize if bleeding spots appear.",
        "expected_meds": ["Dolo"],
        "expected_diag": ["dengue"],
    },
    {
        "id": "case_23",
        "category": "Infectious Disease",
        "transcript": "Fever with severe shivering and rigors every alternate day. Malaria vivax. Prescribe Chloroquine 600mg base stat, then 300mg at 6, 24, 48 hours, followed by Primaquine 15mg daily for 14 days after G6PD testing. Peripheral smear for malarial parasite. Review in 1 week.",
        "expected_meds": ["Chloroquine", "Primaquine"],
        "expected_diag": ["malaria"],
    },
    {
        "id": "case_24",
        "category": "Infectious Disease",
        "transcript": "Cough for 3 weeks with evening low grade fever, night sweats and weight loss. Pulmonary tuberculosis suspected. Start AKT-4 four tablets daily on empty stomach in morning, and Pyridoxine 20mg OD. Sputum AFB and GeneXpert test, Chest X-ray. Complete 6 months course without missing any dose.",
        "expected_meds": ["AKT-4", "Pyridoxine"],
        "expected_diag": ["tuberculosis"],
    },
    {
        "id": "case_25",
        "category": "Infectious Disease",
        "transcript": "Burning micturition, increased frequency and lower abdominal discomfort. Urinary tract infection. Prescribe Nitrofurantoin 100mg BD for 7 days, Urispas 200mg TDS for bladder spasm, and Citralka liquid 2 teaspoons in glass of water TDS. Urine routine and microscopy. Drink 3 liters of water daily.",
        "expected_meds": ["Nitrofurantoin", "Urispas", "Citralka"],
        "expected_diag": ["urinary tract infection"],
    },

    # ── Orthopedics & Rheumatology (26-30) ──
    {
        "id": "case_26",
        "category": "Orthopedics",
        "transcript": "Severe right knee joint pain and morning stiffness. Osteoarthritis of knee. Prescribe Zerodol-SP 1 tablet BD after food for 5 days, Pan-40 OD before breakfast, and Cartigen Forte 1 tablet daily for 1 month. Apply Volini gel topically TDS. Quadriceps strengthening exercises. Review in 2 weeks.",
        "expected_meds": ["Zerodol-SP", "Pan-40", "Cartigen"],
        "expected_diag": ["osteoarthritis"],
    },
    {
        "id": "case_27",
        "category": "Orthopedics",
        "transcript": "Sudden onset excruciating pain and swelling in the first metatarsophalangeal big toe joint. Acute gouty arthritis. Prescribe Indomethacin 50mg TDS after food for 3 days, Colchicine 0.5mg BD, and Pantocid 40mg OD. Serum uric acid test. Avoid red meat, alcohol, and purine rich foods. Follow up in 5 days.",
        "expected_meds": ["Indomethacin", "Colchicine", "Pantocid"],
        "expected_diag": ["gout"],
    },
    {
        "id": "case_28",
        "category": "Orthopedics",
        "transcript": "Severe lower back ache radiating to left lower limb with tingling. Lumbar disc herniation with sciatica. Give Gabapentin 300mg at bedtime, Nucoxia 90mg OD after food for 5 days, and Myoril 4mg BD for muscle spasm. MRI Lumbar Spine. Strict bed rest on firm mattress, avoid bending forward.",
        "expected_meds": ["Gabapentin", "Nucoxia", "Myoril"],
        "expected_diag": ["sciatica", "disc"],
    },
    {
        "id": "case_29",
        "category": "Orthopedics",
        "transcript": "Symmetrical small joint swelling and pain in both hands for 3 months with morning stiffness lasting 1 hour. Rheumatoid arthritis. Start Methotrexate 10mg once weekly, Folic acid 5mg next day, and Defcort 6mg OD morning. RA factor, Anti-CCP, ESR, and LFT. Review after 4 weeks.",
        "expected_meds": ["Methotrexate", "Folic acid", "Defcort"],
        "expected_diag": ["rheumatoid arthritis"],
    },
    {
        "id": "case_30",
        "category": "Orthopedics",
        "transcript": "Neck stiffness and tingling numbness in fingers of right hand. Cervical spondylosis. Prescribe Ultracet one tablet BD for 5 days, Neurobion Forte one tablet daily for 1 month, and Robaxin 500mg BD. Cervical collar during travel, avoid heavy pillows. Isometric neck exercises.",
        "expected_meds": ["Ultracet", "Neurobion", "Robaxin"],
        "expected_diag": ["cervical spondylosis"],
    },

    # ── Dermatology (31-35) ──
    {
        "id": "case_31",
        "category": "Dermatology",
        "transcript": "Itchy ring-shaped red scaling patches in groins and thighs. Tinea cruris fungal infection. Prescribe Itraconazole 100mg BD after meals for 14 days, Luliconazole 1% cream apply twice daily for 3 weeks, and Levocetirizine 5mg at bedtime. Wear loose cotton clothes, keep area dry.",
        "expected_meds": ["Itraconazole", "Luliconazole", "Levocetirizine"],
        "expected_diag": ["tinea"],
    },
    {
        "id": "case_32",
        "category": "Dermatology",
        "transcript": "Intense itching between fingers and wrists worse at night. Scabies. Prescribe Permethrin 5% lotion apply neck down overnight and wash off after 10 hours, repeat after 7 days. Atarax 25mg at night for itching. Treat all family members simultaneously. Wash bedding in hot water.",
        "expected_meds": ["Permethrin", "Atarax"],
        "expected_diag": ["scabies"],
    },
    {
        "id": "case_33",
        "category": "Dermatology",
        "transcript": "Papules, pustules, and comedones over face. Moderate acne vulgaris. Start Clindamycin gel apply morning, Nadifloxacin cream at night, and Doxycycline 100mg once daily after food for 4 weeks. Wash face with mild salicylic acid cleanser twice daily. Avoid picking spots.",
        "expected_meds": ["Clindamycin", "Nadifloxacin", "Doxycycline"],
        "expected_diag": ["acne"],
    },
    {
        "id": "case_34",
        "category": "Dermatology",
        "transcript": "Erythematous plaques with silvery scales over extensor elbows and knees. Plaque psoriasis. Prescribe Clobetasol 0.05% ointment apply BD for 2 weeks, Calcipotriol ointment apply at night, and Cetaphil moisturizing cream liberally. Avoid stress, sun exposure recommended. Review in 1 month.",
        "expected_meds": ["Clobetasol", "Calcipotriol", "Cetaphil"],
        "expected_diag": ["psoriasis"],
    },
    {
        "id": "case_35",
        "category": "Dermatology",
        "transcript": "Transient itchy wheals and hives over trunk and limbs for 2 days. Acute urticaria. Give Bilastine 20mg OD on empty stomach 1 hour before breakfast for 10 days, Avil 25mg SOS for severe itching, and Calamine lotion topically. Avoid suspected seafood and NSAIDs. Review in 5 days.",
        "expected_meds": ["Bilastine", "Avil", "Calamine"],
        "expected_diag": ["urticaria"],
    },

    # ── Neurology & Psychiatry (36-40) ──
    {
        "id": "case_36",
        "category": "Neurology",
        "transcript": "Unilateral throbbing headache with nausea and photophobia lasting 12 hours. Acute migraine attack. Prescribe Rizact 10mg stat for attack, Naproxen 500mg with Domperidone 10mg stat. Propranolol 40mg OD for prophylaxis. Brain MRI not indicated right now. Rest in a dark quiet room.",
        "expected_meds": ["Rizact", "Naproxen", "Propranolol"],
        "expected_diag": ["migraine"],
    },
    {
        "id": "case_37",
        "category": "Neurology",
        "transcript": "Rotational spinning sensation on turning head in bed, with vomiting. Benign paroxysmal positional vertigo. Prescribe Vertin 16mg TDS for 5 days, Stugeron 25mg BD, and Ondansetron 4mg SOS. Epley maneuver performed today. Avoid sudden head movements. Review in 3 days.",
        "expected_meds": ["Vertin", "Stugeron", "Ondansetron"],
        "expected_diag": ["vertigo"],
    },
    {
        "id": "case_38",
        "category": "Neurology",
        "transcript": "Tremors at rest in right hand, rigidity, and slowed movements. Parkinson's disease. Start Syndopa Plus half tablet TDS after meals, increase to 1 tablet TDS after 1 week, and Pacitane 2mg BD. Brain MRI. Physiotherapy and gait training. Review after 3 weeks.",
        "expected_meds": ["Syndopa", "Pacitane"],
        "expected_diag": ["parkinson"],
    },
    {
        "id": "case_39",
        "category": "Psychiatry",
        "transcript": "Persistent low mood, lack of interest, early morning awakening, and fatigue for 2 months. Major depressive disorder. Prescribe Nexito 10mg once daily in morning after breakfast, and Clonazepam 0.25mg at bedtime for 10 days only. Cognitive behavioral therapy. Emergency contact given. Review in 2 weeks.",
        "expected_meds": ["Nexito", "Clonazepam"],
        "expected_diag": ["depression"],
    },
    {
        "id": "case_40",
        "category": "Psychiatry",
        "transcript": "Excessive worry, tremors, palpitations, and restlessness during exams. Generalized anxiety disorder. Start Etilaam 0.5mg at bedtime for 7 days, and Inderal 10mg BD as needed for palpitations. Deep breathing relaxation techniques. Follow up in 10 days.",
        "expected_meds": ["Etilaam", "Inderal"],
        "expected_diag": ["anxiety"],
    },

    # ── Pediatrics & Liquid Formulations (41-45) ──
    {
        "id": "case_41",
        "category": "Pediatrics",
        "transcript": "Child 4 years old, weight 15 kg with fever and cough for 2 days. Viral URTI. Prescribe Calpol syrup 250mg/5ml give 5ml TDS for fever, Ascoril-D junior syrup 2.5ml BD for cough, and Nasoclear saline nasal drops 2 drops each nostril TDS. Sponge with lukewarm water if fever exceeds 101 F. Review in 3 days.",
        "expected_meds": ["Calpol", "Ascoril", "Nasoclear"],
        "expected_diag": ["URTI", "fever"],
    },
    {
        "id": "case_42",
        "category": "Pediatrics",
        "transcript": "Child 6 years old with acute earache and fever. Acute suppurative otitis media. Give Novamox syrup 250mg give 5ml TDS for 7 days, Meftal-P syrup 5ml SOS for pain, and Otrivin pediatric nasal drops BD for 3 days. Do not put oil in ear. Follow up in 5 days.",
        "expected_meds": ["Novamox", "Meftal-P", "Otrivin"],
        "expected_diag": ["otitis media"],
    },
    {
        "id": "case_43",
        "category": "Pediatrics",
        "transcript": "Toddler 2 years old with vomiting and loose green stools. Pediatric acute gastroenteritis. Give Ondem syrup 2ml half hour before feeds, Enterogermina oral suspension 1 mini bottle daily for 5 days, and Zinconia syrup 5ml OD for 14 days. Continue breastfeeding and ORS. Watch for sunken eyes or lethargy.",
        "expected_meds": ["Ondem", "Enterogermina", "Zinconia"],
        "expected_diag": ["gastroenteritis"],
    },
    {
        "id": "case_44",
        "category": "Pediatrics",
        "transcript": "Child 8 years old with recurrent wheezing and nighttime coughing. Childhood asthma. Start Asthalin respules 2.5mg nebulization BD for 3 days, Budecort respules 0.5mg nebulization BD for 5 days, and Montair-LC kid chewable tablet 1 tablet at night. Pediatric chest review in 1 week.",
        "expected_meds": ["Asthalin", "Budecort", "Montair-LC"],
        "expected_diag": ["asthma"],
    },
    {
        "id": "case_45",
        "category": "Pediatrics",
        "transcript": "Child 5 years old with perianal itching at night and teeth grinding. Enterobiasis pinworm infection. Prescribe Zentel suspension 400mg single dose 10ml at night, repeat dose after 2 weeks. Cut nails short, wash hands before eating, treat all family members.",
        "expected_meds": ["Zentel"],
        "expected_diag": ["pinworm", "infection"],
    },

    # ── Nephrology, Urology & Ophthalmology (46-50) ──
    {
        "id": "case_46",
        "category": "Urology",
        "transcript": "Elderly gentleman with weak urinary stream, hesitancy and nocturia 4 times. Benign prostatic hyperplasia BPH. Prescribe Urimax-D one capsule once daily at bedtime for 3 months. Serum PSA test, Ultrasound KUB with post void residual volume. Avoid excessive fluids after 8 PM. Review in 1 month.",
        "expected_meds": ["Urimax-D"],
        "expected_diag": ["benign prostatic hyperplasia", "BPH"],
    },
    {
        "id": "case_47",
        "category": "Urology",
        "transcript": "Right flank pain radiating to groin with microscopic hematuria. Right ureteric calculus 5mm stone. Prescribe Tamflo 0.4mg OD at night for medical expulsive therapy, Ketorol-DT 10mg SOS for severe pain, and Cital syrup 2 spoons in water TDS. Drink 4 liters of fluid daily. Strain urine for stone passage.",
        "expected_meds": ["Tamflo", "Ketorol", "Cital"],
        "expected_diag": ["calculus", "stone"],
    },
    {
        "id": "case_48",
        "category": "Ophthalmology",
        "transcript": "Redness, grittiness, and sticky yellow discharge from left eye. Bacterial conjunctivitis. Prescribe Moxicip eye drops 1 drop 4 times daily in left eye for 7 days, and Refresh Tears eye drops 1 drop TDS. Avoid rubbing eye, wash hands frequently, use separate towel. Review in 4 days.",
        "expected_meds": ["Moxicip", "Refresh Tears"],
        "expected_diag": ["conjunctivitis"],
    },
    {
        "id": "case_49",
        "category": "Dentistry",
        "transcript": "Severe throbbing toothache in right lower molar with sensitivity to hot foods. Acute pulpitis. Prescribe Ketorolac 10mg TDS after food for 3 days, Augmentin 625mg BD for 5 days, and Rexidin mouthwash rinse BD. Dental X-ray IOPA of tooth 46. Root canal treatment recommended.",
        "expected_meds": ["Ketorolac", "Augmentin", "Rexidin"],
        "expected_diag": ["pulpitis", "toothache"],
    },
    {
        "id": "case_50",
        "category": "Gynecology",
        "transcript": "Irregular menstrual cycles, hirsutism, and acne in 22-year-old female. Polycystic ovarian syndrome PCOS. Start Krimson-35 1 tablet daily starting day 1 of cycle for 21 days for 3 cycles, Metformin 500mg BD with food, and Inositol sachet OD. Pelvic Ultrasound and hormonal profile. Weight reduction and exercise.",
        "expected_meds": ["Krimson-35", "Metformin", "Inositol"],
        "expected_diag": ["PCOS", "polycystic ovarian"],
    },
]


def run_benchmark():
    print("=" * 70)
    print("BENCHMARKING QWEN2.5 1.5B INSTRUCT ACROSS 50 CLINICAL PRESCRIPTIONS")
    print("=" * 70)

    # 1. Verify model is available
    if not is_available("qwen2.5-1.5b"):
        print("[!] ERROR: Qwen2.5 1.5B model is not available or llama_cpp is missing.")
        return

    print("[*] Loading Qwen2.5 1.5B model...")
    t0 = time.time()
    model = load_model("qwen2.5-1.5b")
    print(f"[+] Model loaded in {time.time() - t0:.1f}s\n")

    results = []
    med_match_count = 0
    total_meds_expected = 0
    total_meds_extracted = 0
    diag_match_count = 0
    total_cases = len(BENCHMARK_CASES)

    for i, case in enumerate(BENCHMARK_CASES, 1):
        cid = case["id"]
        category = case["category"]
        transcript = case["transcript"]
        exp_meds = case["expected_meds"]
        exp_diag = case["expected_diag"]

        # Run pipeline: Regex Draft -> LLM Refinement
        draft = normalize_entities(extract(transcript))
        t_start = time.time()
        refined = llm_refine(transcript, draft, model_key="qwen2.5-1.5b")
        t_elapsed = time.time() - t_start

        extracted_meds = [m.get("name", "") for m in refined.get("medications", [])]
        extracted_diag = [str(d) for d in refined.get("diagnosis", [])]
        extracted_inv = [str(x) for x in refined.get("investigations", [])]
        follow_up = refined.get("follow_up", "")

        # Evaluation metrics: Medication recall (matches by Brand name or Generic compound)
        from clinical.medicines import lookup
        meds_found = []
        for em in exp_meds:
            em_info = lookup(em)
            em_generic = em_info.get("generic", "").lower() if em_info else ""
            found = False
            for m in extracted_meds:
                m_info = lookup(m)
                m_generic = m_info.get("generic", "").lower() if m_info else ""
                if (em.lower() in m.lower()) or (m.lower() in em.lower()):
                    found = True
                    break
                if em_generic and (em_generic in m.lower() or em_generic == m_generic):
                    found = True
                    break
            if found:
                meds_found.append(em)

        med_match_count += len(meds_found)
        total_meds_expected += len(exp_meds)
        total_meds_extracted += len(extracted_meds)

        # Diagnosis recall
        diag_found = any(
            any(ed.lower() in d.lower() for d in extracted_diag)
            for ed in exp_diag
        )
        if diag_found:
            diag_match_count += 1

        score = (len(meds_found) / len(exp_meds)) * 100 if exp_meds else 100
        status_sym = "[OK]" if score >= 80 and diag_found else "[PARTIAL]"

        print(f"[{i:02d}/50] {status_sym} ({category:<18}) {cid} | Time: {t_elapsed:.2f}s | Meds: {len(meds_found)}/{len(exp_meds)} | Diag: {'Yes' if diag_found else 'No'}")
        if score < 100 or not diag_found:
            print(f"       Expected Meds: {exp_meds} -> Got: {extracted_meds}")
            print(f"       Expected Diag: {exp_diag} -> Got: {extracted_diag}")

        results.append({
            "case_id": cid,
            "category": category,
            "time_sec": t_elapsed,
            "med_score": score,
            "diag_found": diag_found,
            "extracted_meds": extracted_meds,
            "extracted_diag": extracted_diag,
            "extracted_inv": extracted_inv,
        })

    # Summary
    med_recall = (med_match_count / total_meds_expected) * 100 if total_meds_expected else 0
    diag_accuracy = (diag_match_count / total_cases) * 100
    avg_latency = sum(r["time_sec"] for r in results) / len(results)

    print("\n" + "=" * 70)
    print("BENCHMARK SUMMARY RESULTS:")
    print("=" * 70)
    print(f"  Total Prescriptions Tested: {total_cases}")
    print(f"  Medication Recall:          {med_recall:.1f}% ({med_match_count}/{total_meds_expected})")
    print(f"  Diagnosis Detection Rate:   {diag_accuracy:.1f}% ({diag_match_count}/{total_cases})")
    print(f"  Average Extraction Time:    {avg_latency:.2f} seconds / prescription")
    print("=" * 70)

    # Save detailed JSON report
    report_file = os.path.join(os.path.dirname(__file__), "benchmark_50_results.json")
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump({
            "summary": {
                "total_cases": total_cases,
                "med_recall_percent": med_recall,
                "diag_accuracy_percent": diag_accuracy,
                "avg_latency_sec": avg_latency,
            },
            "cases": results,
        }, f, indent=2)
    print(f"[+] Detailed report saved to: {report_file}")


if __name__ == "__main__":
    run_benchmark()
