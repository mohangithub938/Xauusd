from __future__ import annotations
import smtplib, ssl
from email.message import EmailMessage

def validate(sender,app_password,recipient):
    missing=[]
    if not sender: missing.append("Sender Gmail")
    if not app_password: missing.append("Gmail App Password")
    if not recipient: missing.append("Recipient email")
    return (False,"Missing: "+", ".join(missing)) if missing else (True,"Gmail settings complete.")

def send(sender,app_password,recipient,subject,body):
    ok,msg=validate(sender,app_password,recipient)
    if not ok: raise ValueError(msg)
    email=EmailMessage()
    email["From"]=sender; email["To"]=recipient; email["Subject"]=subject
    email.set_content(body)
    try:
        with smtplib.SMTP_SSL("smtp.gmail.com",465,context=ssl.create_default_context(),timeout=15) as smtp:
            smtp.login(sender,app_password.replace(" ",""))
            smtp.send_message(email)
    except smtplib.SMTPAuthenticationError as exc:
        raise RuntimeError("Gmail authentication failed. Use the 16-character Google App Password.") from exc
    except Exception as exc:
        raise RuntimeError(f"Gmail send failed: {exc}") from exc
