# Szükséges importok
import streamlit as st
import pandas as pd
import sqlite3
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Tokenizer és modell betöltése
tokenizer = AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-128k-instruct", trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained("microsoft/DialoGPT-small")

# Adatbázis kapcsolat és felhasználói tábla létrehozása
conn = sqlite3.connect('felhasznalok.db')
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS felhasznalok
             (felhasznalo_nev TEXT PRIMARY KEY, elofizetesi_szint TEXT)''')
conn.commit()

# Új felhasználó hozzáadása az adatbázishoz
def hozzaad_felhasznalo(felhasznalo_nev, elofizetesi_szint):
    with conn:
        c.execute("INSERT OR REPLACE INTO felhasznalok (felhasznalo_nev, elofizetesi_szint) VALUES (?, ?)", 
                  (felhasznalo_nev, elofizetesi_szint))

# Felhasználó előfizetési szint lekérdezése
def lekerdezes_felhasznalo(felhasznalo_nev):
    c.execute("SELECT elofizetesi_szint FROM felhasznalok WHERE felhasznalo_nev = ?", (felhasznalo_nev,))
    eredmeny = c.fetchone()
    return eredmeny[0] if eredmeny else "nincs"

# Hitelesítés és előfizetés kezeléshez szükséges osztályok
class FelhasznaloiHitelesites:
    def __init__(self, felhasznalo_id):
        self.felhasznalo_id = felhasznalo_id
        self.elofizetesi_szint = lekerdezes_felhasznalo(felhasznalo_id)
    
    def hitelesitett(self):
        return self.elofizetesi_szint != "nincs"

class ElofizetesKezeles:
    def __init__(self, hitelesites):
        self.hitelesites = hitelesites
    
    def van_eleg_jogosultsag(self):
        return self.hitelesites.elofizetesi_szint in ["premium", "enterprise"]

class KapacitasEllenorzo:
    def __init__(self, termek):
        self.termek = termek  # Szótár a termekről és azok kapacitásáról

    def kapacitas_ellenorzes(self, terem_nev, letszam, foglalasok):
        # Számoljuk ki az adott terem szabad kapacitását
        foglalt_helyek = foglalasok.get(terem_nev, 0)
        maradek_hely = self.termek.get(terem_nev, 0) - foglalt_helyek
        return maradek_hely >= letszam

# Válasz generáló függvény
def general_valasz(bemeneti_szoveg, max_hossz=100):
    bemenetek = tokenizer(bemeneti_szoveg, return_tensors="pt")
    kimenetek = model.generate(**bemenetek, max_length=max_hossz, pad_token_id=tokenizer.eos_token_id)
    valasz = tokenizer.decode(kimenetek[0], skip_special_tokens=True)
    return valasz

# Streamlit UI
st.title("Sales Support AI Chatbot")

# Új felhasználó hozzáadása
st.subheader("Új felhasználó hozzáadása")
uj_felhasznalo_nev = st.text_input("Új felhasználó neve:", key="uj_felhasznalo")
uj_elofizetesi_szint = st.selectbox("Előfizetési szint:", ["ingyenes", "premium", "enterprise"], key="uj_elofizetesi_szint")

if st.button("Felhasználó hozzáadása"):
    if uj_felhasznalo_nev:
        hozzaad_felhasznalo(uj_felhasznalo_nev, uj_elofizetesi_szint)
        st.success(f"{uj_felhasznalo_nev} hozzáadva {uj_elofizetesi_szint} előfizetéssel.")
    else:
        st.error("Kérjük, adjon meg egy felhasználónevet.")

# Felhasználó hitelesítése
st.subheader("Felhasználói bejelentkezés")
felhasznalo_id = st.text_input("Adja meg a felhasználói azonosítót:", key="felhasznalo_bejelentkezes")
hitelesites = FelhasznaloiHitelesites(felhasznalo_id=felhasznalo_id)
elofizetes_kezeles = ElofizetesKezeles(hitelesites)

# Teremkapacitás beállítása
termek = {
    "Fő terem": 100,
    "A konferenciaterem": 50,
    "Bálterem": 150
}
kapacitas_ellenorzo = KapacitasEllenorzo(termek)

# Foglalási táblázat feltöltése
st.subheader("Foglalási táblázat feltöltése")
feltoltott_fajl = st.file_uploader("Töltsön fel egy foglalási táblázatot (CSV vagy Excel formátum)", type=["csv", "xlsx"])

if feltoltott_fajl:
    if feltoltott_fajl.name.endswith("csv"):
        foglalasok_df = pd.read_csv(feltoltott_fajl)
    else:
        foglalasok_df = pd.read_excel(feltoltott_fajl)

    # Összesítjük a foglalt helyeket teremenként
    foglalasok = foglalasok_df.groupby('terem_nev')['letszam'].sum().to_dict()
    st.write("Feltöltött foglalások összesítve:", foglalasok)

if hitelesites.hitelesitett() and elofizetes_kezeles.van_eleg_jogosultsag():
    st.success("Hitelesített felhasználó és elegendő jogosultság.")

    # E-mail tartalom megadása és terem választás
    email_tartalom = st.text_area("E-mail tartalom:")
    terem_nev = st.selectbox("Válassza ki a foglalni kívánt termet:", list(termek.keys()))
    letszam = st.number_input("Vendégek száma:", min_value=1, max_value=500, value=50)

    # Kapacitás ellenőrzés és válasz generálás
    if st.button("Foglalás ellenőrzése és válasz generálása"):
        if feltoltott_fajl:
            if kapacitas_ellenorzo.kapacitas_ellenorzes(terem_nev, letszam, foglalasok):
                st.success("A terem elérhető.")
                # Válasz generálása az e-mail alapján
                valasz = general_valasz(email_tartalom)
                st.write("Generált válasz:")
                st.write(valasz)
            else:
                st.error("A kért terem kapacitása nem elegendő.")
        else:
            st.warning("Kérjük, töltsön fel foglalási táblázatot.")
else:
    if not hitelesites.hitelesitett():
        st.warning("Nem hitelesített felhasználó.")
    elif not elofizetes_kezeles.van_eleg_jogosultsag():
        st.warning("Nincs elegendő előfizetés.")
