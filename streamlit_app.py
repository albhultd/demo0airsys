# Szükséges importok
import streamlit as st
from transformers import AutoTokenizer, AutoModelForCausalLM
import torch

# Tokenizer és modell betöltése
tokenizer = AutoTokenizer.from_pretrained("microsoft/Phi-3-mini-128k-instruct", trust_remote_code=True)
model = AutoModelForCausalLM.from_pretrained("microsoft/Phi-3-mini-128k-instruct", trust_remote_code=True)



# Hitelesítés és előfizetés kezeléshez szükséges osztályok
class FelhasznaloiHitelesites:
    def __init__(self, felhasznalo_id):
        self.felhasznalo_id = felhasznalo_id
        self.elofizetesi_szint = "ingyenes"  # Példa: lehet "premium" vagy "enterprise" is
    
    def hitelesitett(self):
        # Ide jönne a tényleges hitelesítési logika
        return True

class ElofizetesKezeles:
    def __init__(self, hitelesites):
        self.hitelesites = hitelesites
    
    def van_eleg_jogosultsag(self):
        # Ellenőrzi, hogy a felhasználónak van-e elegendő hozzáférése a válasz generáláshoz
        return self.hitelesites.elofizetesi_szint != "ingyenes"

class KapacitasEllenorzo:
    def __init__(self, termek):
        self.termek = termek  # Szótár a termekről és azok kapacitásáról

    def kapacitas_ellenorzes(self, terem_nev, letszam):
        if terem_nev in self.termek and self.termek[terem_nev] >= letszam:
            return True
        return False

# Válasz generáló függvény
def general_valasz(bemeneti_szoveg, max_hossz=100):
    bemenetek = tokenizer(bemeneti_szoveg, return_tensors="pt")
    kimenetek = model.generate(**bemenetek, max_length=max_hossz, pad_token_id=tokenizer.eos_token_id)
    valasz = tokenizer.decode(kimenetek[0], skip_special_tokens=True)
    return valasz

# Streamlit UI
st.title("Sales Support AI Chatbot")

# Felhasználó hitelesítése
felhasznalo_id = st.text_input("Adja meg a felhasználói azonosítót:")
hitelesites = FelhasznaloiHitelesites(felhasznalo_id=felhasznalo_id)
elofizetes_kezeles = ElofizetesKezeles(hitelesites)

# Teremkapacitás beállítása
termek = {
    "Fő terem": 100,
    "A konferenciaterem": 50,
    "Bálterem": 150
}
kapacitas_ellenorzo = KapacitasEllenorzo(termek)

if hitelesites.hitelesitett() and elofizetes_kezeles.van_eleg_jogosultsag():
    st.success("Hitelesített felhasználó és elegendő jogosultság.")

    # E-mail tartalom megadása és terem választás
    email_tartalom = st.text_area("E-mail tartalom:")
    terem_nev = st.selectbox("Válassza ki a foglalni kívánt termet:", list(termek.keys()))
    letszam = st.number_input("Vendégek száma:", min_value=1, max_value=500, value=50)

    # Kapacitás ellenőrzés és válasz generálás
    if st.button("Foglalás ellenőrzése és válasz generálása"):
        if kapacitas_ellenorzo.kapacitas_ellenorzes(terem_nev, letszam):
            st.success("A terem elérhető.")
            # Válasz generálása az e-mail alapján
            valasz = general_valasz(email_tartalom)
            st.write("Generált válasz:")
            st.write(valasz)
        else:
            st.error("A kért terem kapacitása nem elegendő.")
else:
    st.warning("Nem hitelesített felhasználó vagy nincs elegendő előfizetés.")

