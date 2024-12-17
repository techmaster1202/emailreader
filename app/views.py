from django.http import JsonResponse
from django.views import View
from imaplib import IMAP4_SSL
import email
from email.header import decode_header
from bs4 import BeautifulSoup
import re
from datetime import datetime

# Constants for IMAP server and credentials
IMAP_PORT = 993
IMAP_SERVER = "imap.gmail.com"
EMAIL_ACCOUNTS = [
    {"email": "turoadmin@onyx-rentals.com", "app_password": "mcoi wsxp xqxi vayi"},
    {"email": "turotesting01@gmail.com", "app_password": "ulev ywmu vtbh jtrv"}
]

class ProcessEmailsView(View):
    def extract_details_from_text(self, text):
        details = {
            "car_name_and_year": "",
            "trip_start_date_time": "",
            "trip_end_date_time": "",
            "delivery_location": "",
            "guest_info": {"name": "", "phone_number": ""},
            "reservation_id": ""
        }
        try:
            car_name_and_year_match = re.search(r'Booked trip ([\w\s-]+) (\d{4})', text, re.IGNORECASE)
            start_date_match = re.search(r'from ([A-Za-z]+, \w+ \d{1,2}, \d{4} \d{1,2}:\d{2} (?:AM|PM))', text, re.IGNORECASE)
            end_date_match = re.search(r'to ([A-Za-z]+, \w+ \d{1,2}, \d{4} \d{1,2}:\d{2} (?:AM|PM))', text, re.IGNORECASE)
            guest_name_match = re.search(r'About the guest ([^\(]+)', text, re.IGNORECASE)
            guest_phone_match = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', text, re.IGNORECASE)
            reservation_id_match = re.search(r'Reservation ID[:\s#]*(\w+)', text, re.IGNORECASE)

            if car_name_and_year_match:
                details["car_name_and_year"] = f'{car_name_and_year_match.group(1).strip()} {car_name_and_year_match.group(2)}'
            if start_date_match:
                details["trip_start_date_time"] = start_date_match.group(1).strip()
            if end_date_match:
                details["trip_end_date_time"] = end_date_match.group(1).strip()
            if guest_name_match:
                details["guest_info"]["name"] = guest_name_match.group(1).strip()
            if guest_phone_match:
                details["guest_info"]["phone_number"] = f'{guest_phone_match.group(1)}-{guest_phone_match.group(2)}-{guest_phone_match.group(3)}'
            if reservation_id_match:
                details["reservation_id"] = reservation_id_match.group(1).strip()

        except Exception as e:
            print(f"Error extracting details: {str(e)}")

        return details

    def extract_location_from_html(self, html_content):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            text = soup.get_text(separator=' ', strip=True)

            location_pattern = re.compile(
                r'\b(?:Location|Delivery)\b[^:]*?:?\s*([^:]+?)(?:\s+Extras|\s+Special airport requirements|\s+Review Requirements|\s+About the guest|\s+Guests see:|\s+Download the Turo app|\s+Available on iOS and Android|$)',
                re.DOTALL
            )

            match = location_pattern.search(text)
            if match:
                location_text = match.group(1).strip()
                return location_text

        except Exception as e:
            print(f"Error extracting location: {str(e)}")

        return ""

    def extract_car_id_from_html(self, html_content):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            car_link = soup.find('a', href=re.compile(r"https://turo.com/us/en/car-rental/"))
            if car_link:
                car_url = car_link.get('href')
                car_id = car_url.split('/')[-1]
                return car_id
        except Exception as e:
            print(f"Error extracting car_id: {str(e)}")
        return ""

    def extract_details_from_cancellation_text(self, text):
        details = {
            "car_name_and_year": "",
            "trip_start_date_time": "",
            "trip_end_date_time": "",
            "delivery_location": "",
            "guest_info": {"name": "", "phone_number": ""},
            "reservation_id": ""
        }
        try:
            car_name_and_year_match = re.search(r'(?:Cancelled trip|your) ([\w\s-]+) (\d{4})', text, re.IGNORECASE)
            if not car_name_and_year_match:
                car_name_and_year_match = re.search(r'with your ([\w\s-]+) (\d{4})', text, re.IGNORECASE)

            start_date_match = re.search(r'Trip start (\d{1,2}/\d{1,2}/\d{2,4} \d{1,2}:\d{2} (?:AM|PM))', text, re.IGNORECASE)
            end_date_match = re.search(r'Trip end (\d{1,2}/\d{1,2}/\d{2,4} \d{1,2}:\d{2} (?:AM|PM))', text, re.IGNORECASE)
            guest_name_match = re.search(r'About the guest ([^\(]+?)(?:\sDownload|\sHave|$)', text, re.IGNORECASE)
            reservation_id_match = re.search(r'Reservation ID[:\s#]*(\w+)', text, re.IGNORECASE)
            location_match = re.search(r'Location ([\w\s,.]+?)(?:\sAbout|\sDownload|\sHave|\sContact)', text, re.IGNORECASE)
            guest_phone_match = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', text)

            if car_name_and_year_match:
                details["car_name_and_year"] = f'{car_name_and_year_match.group(1).strip()} {car_name_and_year_match.group(2)}'
            if start_date_match:
                details["trip_start_date_time"] = start_date_match.group(1).strip()
            if end_date_match:
                details["trip_end_date_time"] = end_date_match.group(1).strip()
            if guest_name_match:
                details["guest_info"]["name"] = guest_name_match.group(1).strip()
            if reservation_id_match:
                details["reservation_id"] = reservation_id_match.group(1).strip()
            if location_match:
                details["delivery_location"] = location_match.group(1).strip()
            if guest_phone_match:
                details["guest_info"]["phone_number"] = f'{guest_phone_match.group(1)}-{guest_phone_match.group(2)}-{guest_phone_match.group(3)}'

        except Exception as e:
            print(f"Error extracting details from cancellation email: {str(e)}")

        return details

    def extract_details_from_changed_text(self, text):
        details = {
            "car_name_and_year": "",
            "trip_start_date_time": "",
            "trip_end_date_time": "",
            "delivery_location": "",
            "guest_info": {"name": "", "phone_number": ""},
            "reservation_id": ""
        }

        try:
            car_name_and_year_match = re.search(r'Booked trip ([\w\s-]+) (\d{4})', text, re.IGNORECASE)
            start_date_match = re.search(r'Trip start (\d{1,2}/\d{1,2}/\d{2,4} \d{1,2}:\d{2} (?:AM|PM))', text)
            new_end_date_match = re.search(r'New trip end on ([A-Za-z]+, [A-Za-z]+ \d{1,2} \d{1,2}:\d{2} (?:AM|PM))', text)
            
            if new_end_date_match:
                end_date_str = new_end_date_match.group(1).strip()
                try:
                    end_date_obj = datetime.strptime(end_date_str, "%a, %b %d %I:%M %p")
                    if start_date_match:
                        start_date_str = start_date_match.group(1).strip()
                        start_date_obj = datetime.strptime(start_date_str, "%m/%d/%y %I:%M %p")
                        end_date_obj = end_date_obj.replace(year=start_date_obj.year)
                    details["trip_end_date_time"] = end_date_obj.strftime("%m/%d/%y %I:%M %p")
                except ValueError:
                    details["trip_end_date_time"] = end_date_str
            else:
                end_date_match = re.search(r'Trip end (\d{1,2}/\d{1,2}/\d{2,4} \d{1,2}:\d{2} (?:AM|PM))', text)
                if end_date_match:
                    details["trip_end_date_time"] = end_date_match.group(1).strip()

            if start_date_match:
                details["trip_start_date_time"] = start_date_match.group(1).strip()

            if car_name_and_year_match:
                details["car_name_and_year"] = f'{car_name_and_year_match.group(1).strip()} {car_name_and_year_match.group(2)}'

            guest_name_match = re.search(r'About the guest ([^\(]+)', text)
            guest_phone_match = re.search(r'\((\d{3})\)\s*(\d{3})-(\d{4})', text)
            reservation_id_match = re.search(r'Reservation ID[:\s#]*(\w+)', text)
            location_match = re.search(r'Location ([\w\s,.]+)(?:\sAbout|\sDownload|\sHave|\sContact)', text, re.IGNORECASE)

            if guest_name_match:
                details["guest_info"]["name"] = guest_name_match.group(1).strip()
            if guest_phone_match:
                details["guest_info"]["phone_number"] = f'{guest_phone_match.group(1)}-{guest_phone_match.group(2)}-{guest_phone_match.group(3)}'
            if reservation_id_match:
                details["reservation_id"] = reservation_id_match.group(1).strip()
            if location_match:
                details["delivery_location"] = location_match.group(1).strip()

        except Exception as e:
            print(f"Error extracting details from changed email: {str(e)}")

        return details

    def extract_text_from_html(self, html_body):
        soup = BeautifulSoup(html_body, 'html.parser')
        text = soup.get_text(separator=' ', strip=True)
        return text

    def process_unseen_emails_with_subject(self, mail):
        status, select_response = mail.select("INBOX")
        if status != "OK":
            print("Failed to select INBOX. Exiting.")
            return {"booked_emails": [], "cancelled_emails": [], "edited_emails": []}

        booked_emails = []
        cancelled_emails = []
        edited_emails = []

        booking_search_criteria = '(UNSEEN SUBJECT "is booked!")'
        status, booking_messages = mail.search(None, booking_search_criteria)
        if status == "OK":
            booking_email_ids = booking_messages[0].split()
            for email_id in booking_email_ids:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        email_data = self.process_email_message(msg, "booking_email")
                        booked_emails.append(email_data)

        cancellation_search_criteria = '(UNSEEN SUBJECT "has cancelled" OR UNSEEN SUBJECT "cancelled their trip")'
        status, cancellation_messages = mail.search(None, cancellation_search_criteria)
        if status == "OK":
            cancellation_email_ids = cancellation_messages[0].split()
            for email_id in cancellation_email_ids:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        email_data = self.process_email_message(msg, "cancelled_email")
                        cancelled_emails.append(email_data)

        edited_search_criteria = '(UNSEEN SUBJECT "has changed")'
        status, edited_messages = mail.search(None, edited_search_criteria)
        if status == "OK":
            edited_email_ids = edited_messages[0].split()
            for email_id in edited_email_ids:
                status, msg_data = mail.fetch(email_id, "(RFC822)")
                for response_part in msg_data:
                    if isinstance(response_part, tuple):
                        msg = email.message_from_bytes(response_part[1])
                        email_data = self.process_email_message(msg, "edited_email")
                        edited_emails.append(email_data)

        return {"booked_emails": booked_emails, "cancelled_emails": cancelled_emails, "edited_emails": edited_emails}

    def process_email_message(self, msg, email_type):
        from_ = msg.get("From")
        subject, encoding = decode_header(msg["Subject"])[0]
        if isinstance(subject, bytes):
            subject = subject.decode(encoding if encoding else "utf-8")

        email_data = {
            "subject": subject if subject else "",
            "from": from_,
            "details": {},
            "email_type": email_type
        }

        if msg.is_multipart():
            for part in msg.walk():
                content_type = part.get_content_type()
                payload = part.get_payload(decode=True)
                if payload:
                    try:
                        charset = part.get_content_charset() or 'utf-8'
                        body = payload.decode(charset, errors='replace')
                        if content_type == "text/html":
                            html_content = body
                            text_content = self.extract_text_from_html(body)
                            if email_type == "cancelled_email":
                                email_data["details"] = self.extract_details_from_cancellation_text(text_content)
                            elif email_type == "edited_email":
                                email_data["details"] = self.extract_details_from_changed_text(text_content)
                            else:
                                email_data["details"] = self.extract_details_from_text(text_content)
                            email_data["details"]["delivery_location"] = self.extract_location_from_html(html_content)
                            email_data["details"]["car_id"] = self.extract_car_id_from_html(html_content)
                    except Exception as e:
                        print(f"Error decoding email body: {str(e)}")
        return email_data

    def fetch_emails_for_account(self, email_account, app_password):
        try:
            with IMAP4_SSL(IMAP_SERVER, IMAP_PORT) as mail:
                mail.login(email_account, app_password)
                return self.process_unseen_emails_with_subject(mail)
        except Exception as e:
            print(f"Error processing emails for {email_account}: {str(e)}")
            return {"booked_emails": [], "cancelled_emails": [], "edited_emails": []}

    def get(self, request, *args, **kwargs):
        print("this is called")
        combined_emails = {"booked_emails": [], "cancelled_emails": [], "edited_emails": []}
        try:
            for account in EMAIL_ACCOUNTS:
                print("email " + account["email"])
                email_data = self.fetch_emails_for_account(account["email"], account["app_password"])

                combined_emails["booked_emails"].extend(email_data["booked_emails"])
                combined_emails["cancelled_emails"].extend(email_data["cancelled_emails"])
                combined_emails["edited_emails"].extend(email_data["edited_emails"])

            response_data = {
                "status": "success",
                "message": f"Retrieved {len(combined_emails['booked_emails'])} booking emails, {len(combined_emails['cancelled_emails'])} cancellation emails, and {len(combined_emails['edited_emails'])} edited emails.",
                "emails": combined_emails
            }

            return JsonResponse(response_data, safe=False, json_dumps_params={'indent': 4})

        except Exception as e:
            response_data = {
                "status": "error",
                "message": str(e),
                "emails": []
            }
            return JsonResponse(response_data, status=500, safe=False, json_dumps_params={'indent': 4})
