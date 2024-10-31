import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import re
from transformers import pipeline
import json
import calendar
import plotly.graph_objects as go
from deep_translator import GoogleTranslator
import io

# Konfiguráció és állapot kezelés
class BookingSystem:
    def __init__(self):
        self.rooms = {}
        self.bookings = pd.DataFrame(columns=['date', 'room', 'event_type', 'pax', 'status', 'customer_name', 'email', 'phone'])
        self.supported_languages = ['hu', 'en', 'de', 'fr', 'es']

    def add_room(self, name, capacity, event_types):
        self.rooms[name] = {
            'capacity': capacity,
            'event_types': event_types
        }

    def check_availability(self, date, pax, event_type):
        available_rooms = []
        for room_name, room_info in self.rooms.items():
            if (room_info['capacity'] >= pax and 
                event_type in room_info['event_types']):
                is_booked = self.bookings[
                    (self.bookings['date'] == date) & 
                    (self.bookings['room'] == room_name)
                ].empty
                if is_booked:
                    available_rooms.append(room_name)
        return available_rooms

    def export_bookings(self, format='xlsx'):
        buffer = io.BytesIO()
        
        if format == 'xlsx':
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                self.bookings.to_excel(writer, index=False)
        elif format == 'csv':
            self.bookings.to_csv(buffer, index=False)
        
        buffer.seek(0)
        return buffer

class EmailParser:
    def __init__(self):
        self.classifier = pipeline("zero-shot-classification")
        self.translator = GoogleTranslator(source='auto', target='en')
    
    def detect_language(self, text):
        # Egyszerű nyelv detektálás kulcsszavak alapján
        hu_keywords = ['köszön', 'szeretn', 'időpont', 'foglal']
        en_keywords = ['hello', 'book', 'reservation', 'would like']
        de_keywords = ['hallo', 'buchung', 'reservierung']
        
        text_lower = text.lower()
        
        if any(word in text_lower for word in hu_keywords):
            return 'hu'
        elif any(word in text_lower for word in de_keywords):
            return 'de'
        else:
            return 'en'  # default to English

    def extract_info(self, email_text):
        # Nyelv detektálás
        lang = self.detect_language(email_text)
        
        # Email szöveg fordítása angolra az egységes feldolgozáshoz
        if lang != 'en':
            translated_text = self.translator.translate(email_text)
        else:
            translated_text = email_text
        
        # Dátum keresése (több formátum támogatása)
        date_patterns = [
            r'\d{4}[-/.]\d{1,2}[-/.]\d{1,2}',  # YYYY-MM-DD
            r'\d{1,2}[-/.]\d{1,2}[-/.]\d{4}',  # DD-MM-YYYY
            r'(Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]* \d{1,2},? \d{4}'  # Month DD, YYYY
        ]
        
        dates = []
        for pattern in date_patterns:
            dates.extend(re.findall(pattern, translated_text))
        
        # Létszám keresése (több nyelven)
        pax_pattern = r'\b(\d+)\s*(fő|személy|vendég|person|people|guests|pax|persons|teilnehmer)\b'
        pax_matches = re.findall(pax_pattern, translated_text.lower())
        
        # Kontakt információk keresése
        email_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
        phone_pattern = r'\+?\d{1,4}?[-.\s]?\(?\d{1,3}?\)?[-.\s]?\d{1,4}[-.\s]?\d{1,4}[-.\s]?\d{1,9}'
        
        emails = re.findall(email_pattern, email_text)
        phones = re.findall(phone_pattern, email_text)
        
        # Név keresése (egyszerű megközelítés)
        name_pattern = r'([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)'
        names = re.findall(name_pattern, email_text)
        
        # Esemény típus felismerése
        event_types = ["wedding", "corporate event", "birthday", "conference"]
        event_type = self.classifier(
            translated_text, 
            candidate_labels=event_types
        )['labels'][0]
        
        return {
            'date': dates[0] if dates else None,
            'pax': int(pax_matches[0][0]) if pax_matches else None,
            'event_type': event_type,
            'email': emails[0] if emails else None,
            'phone': phones[0] if phones else None,
            'name': names[0] if names else None,
            'detected_language': lang
        }

class CalendarView:
    def __init__(self, booking_system):
        self.booking_system = booking_system
    
    def generate_calendar(self, year, month):
        # Naptár adatok generálása
        cal = calendar.monthcalendar(year, month)
        month_name = calendar.month_name[month]
        
        # Foglalások lekérése az adott hónapra
        month_bookings = self.booking_system.bookings[
            pd.to_datetime(self.booking_system.bookings['date']).dt.month == month
        ]
        
        # Plotly figure létrehozása
        fig = go.Figure()
        
        # Naptár cella méretei
        cell_height = 60
        cell_width = 100
        
        # Fejléc hozzáadása
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        for i, day in enumerate(days):
            fig.add_annotation(
                x=i * cell_width + cell_width/2,
                y=cell_height * 6,
                text=day,
                showarrow=False
            )
        
        # Napok és foglalások megjelenítése
        for week_num, week in enumerate(cal):
            for day_num, day in enumerate(week):
                if day != 0:
                    # Nap számának megjelenítése
                    fig.add_annotation(
                        x=day_num * cell_width + 10,
                        y=(5-week_num) * cell_height + cell_height - 10,
                        text=str(day),
                        showarrow=False,
                        align='left'
                    )
                    
                    # Foglalások megjelenítése az adott napra
                    day_bookings = month_bookings[
                        pd.to_datetime(month_bookings['date']).dt.day == day
                    ]
                    
                    for idx, booking in day_bookings.iterrows():
                        fig.add_annotation(
                            x=day_num * cell_width + cell_width/2,
                            y=(5-week_num) * cell_height + cell_height/2,
                            text=f"{booking['room']}\n{booking['event_type']}",
                            showarrow=False,
                            bgcolor='rgba(0,0,255,0.1)'
                        )
        
        # Figure beállítások
        fig.update_layout(
            showlegend=False,
            height=500,
            width=800,
            title=f"{month_name} {year}",
            plot_bgcolor='white'
        )
        
        return fig

# Streamlit alkalmazás
def main():
    st.set_page_config(layout="wide")
    st.title("Éttermi Foglalási Asszisztens")
    
    # Rendszer inicializálása
    if 'booking_system' not in st.session_state:
        st.session_state.booking_system = BookingSystem()
        st.session_state.email_parser = EmailParser()
        st.session_state.calendar_view = CalendarView(st.session_state.booking_system)

    # Oldalsáv a termek kezeléséhez
    with st.sidebar:
        st.header("Terem Beállítások")
        
        with st.form("new_room"):
            room_name = st.text_input("Terem neve")
            capacity = st.number_input("Kapacitás (fő)", min_value=1)
            event_types = st.multiselect(
                "Esemény típusok",
                ["esküvő", "céges rendezvény", "születésnap", "konferencia"]
            )
            
            if st.form_submit_button("Terem Hozzáadása"):
                st.session_state.booking_system.add_room(room_name, capacity, event_types)
                st.success(f"Terem hozzáadva: {room_name}")
        
        # Export funkciók
        st.header("Exportálás")
        export_format = st.selectbox("Export formátum", ['xlsx', 'csv'])
        if st.button("Foglalások Exportálása"):
            buffer = st.session_state.booking_system.export_bookings(export_format)
            st.download_button(
                label=f"Foglalások letöltése ({export_format})",
                data=buffer,
                file_name=f"foglalasok.{export_format}",
                mime="application/vnd.ms-excel" if export_format == 'xlsx' else "text/csv"
            )

    # Fő tartalom
    tab1, tab2, tab3 = st.tabs(["Email Feldolgozás", "Foglalási Táblázat", "Naptár Nézet"])
    
    # Email feldolgozás tab
    with tab1:
        st.header("Email Feldolgozás")
        email_text = st.text_area("Vendég email szövege", height=200)
        
        if st.button("Email Feldolgozása"):
            if email_text:
                # Email feldolgozása
                info = st.session_state.email_parser.extract_info(email_text)
                
                # Eredmények megjelenítése
                st.subheader("Kinyert információk")
                st.json(info)
                
                if all([info['date'], info['pax'], info['event_type']]):
                    # Elérhetőség ellenőrzése
                    available_rooms = st.session_state.booking_system.check_availability(
                        info['date'],
                        info['pax'],
                        info['event_type']
                    )
                    
                    # Válasz generálása az eredeti nyelven
                    is_available = len(available_rooms) > 0
                    response_text = generate_response(
                        is_available, 
                        available_rooms, 
                        info['detected_language']
                    )
                    
                    st.subheader("Generált válasz")
                    st.write(response_text)
                else:
                    st.error("Nem sikerült minden szükséges információt kinyerni az emailből")
    
    # Foglalási táblázat tab
    with tab2:
        st.header("Foglalási Táblázat")
        uploaded_file = st.file_uploader("Foglalási táblázat feltöltése", type=['csv', 'xlsx'])
        
        if uploaded_file:
            try:
                if uploaded_file.name.endswith('.csv'):
                    bookings_df = pd.read_csv(uploaded_file)
                else:
                    bookings_df = pd.read_excel(uploaded_file)
                
                st.session_state.booking_system.bookings = bookings_df
                st.success("Foglalási táblázat sikeresen feltöltve!")
                st.dataframe(bookings_df)
            except Exception as e:
                st.error(f"Hiba a fájl feldolgozása során: {str(e)}")
    
    # Naptár nézet tab
    with tab3:
        st.header("Naptár Nézet")
        col1, col2 = st.columns(2)
        with col1:
            selected_year = st.selectbox("Év", range(2024, 2026))
        with col2:
            selected_month = st.selectbox("Hónap", range(1, 13), format_func=lambda x: calendar.month_name[x])
        
        calendar_fig = st.session_state.calendar_view.generate_calendar(selected_year, selected_month)
        st.plotly_chart(calendar_fig)

def generate_response(is_available, room_names=None, lang='hu'):
    responses = {
        'hu': {
            'available': f"""
            Köszönjük érdeklődését!
            
            Örömmel értesítjük, hogy a kért időpontban van szabad termünk az Ön által tervezett rendezvény lebonyolítására.
            Elérhető termek: {', '.join(room_names) if room_names else ''}
            
            Szívesen egyeztetünk személyesen a további részletekről.
            
            Üdvözlettel,
            [Étterem neve]
            """,
            'not_available': """
            Köszönjük érdeklődését!
            
            Sajnálattal tájékoztatjuk, hogy a kért időpontban sajnos minden termünk foglalt.
            Amennyiben az időpont rugalmas, szívesen ajánlunk alternatív lehetőségeket.
            
            Üdvözlettel,
            [Étterem neve]
            """
        },
        'en': {
            'available': f"""
            Thank you for your inquiry!
            
            We are pleased to inform you that we have available rooms for your planned event.
            Available rooms: {', '.join(room_names) if room_names else ''}
            
            We would be happy to discuss the details in person.
            
            Best regards,
            [Restaurant name]
            """,
            'not_available': """
            Thank you for your inquiry!
            
            Unfortunately, all our rooms are booked for the requested date.
            If your date is flexible, we would be happy to suggest alternative options.
            
            Best regards,
            [Restaurant name]
            """
        },
        'de': {
            'available': f"""
            Vielen Dank für Ihre Anfrage!