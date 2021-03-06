""" This file contains email sending functions for Flask-User.
    It uses Jinja2 to render email subject and email message. It uses Flask-Mail to send email.

    :copyright: (c) 2013 by Ling Thio
    :author: Ling Thio (ling.thio@gmail.com)
    :license: Simplified BSD License, see LICENSE.txt for more details."""

import json
import smtplib
import socket
from flask import current_app, render_template

from sendgrid.helpers.mail import CustomArg, Content, Email, Mail, Personalization

def send_email(*args):
    if current_app.config["mail"] == "sendgrid":
        sg_send_email(*args)
    else:
        flask_send_email(*args)
    
def sg_send_email(recipient, subject, html_message, text_message, typ):
    """ Send email from default sender to 'recipient' using SendGrid """
    mail = Mail()

    # set the to address
    p = Personalization()
    p.add_to(Email(recipient))
    mail.add_personalization(p)

    # add subject line
    mail.set_subject(subject)

    # create from_addr and friendly_from and add
    # from_addr to unique args so we can pull out
    # sending_domain in the email event webhandler
    from_addr = current_app.config["MAIL_FROM_ADDR"]
    friendly_from = current_app.config["MAIL_FRIENDLY_FROM"]
    mail.set_from(Email(email=from_addr, name=friendly_from))
    mail.add_custom_arg(CustomArg(key="from_addr", value=from_addr))

    # generate the token and add it as a unique arg
    send_token = current_app.token_manager.get_next_token()
    mail.add_custom_arg(CustomArg(key="token", value=send_token))

    # make token substitutes in the content
    _TOKEN_PARAMS = ("[[ TOKEN ]]", "[[TOKEN]]", "[[ token ]]", "[[token]]")
    for _PARAM in _TOKEN_PARAMS:
        text_message = text_message.replace(_PARAM, send_token)
        html_message = html_message.replace(_PARAM, send_token)

    mail.add_content(Content(type="text/plain", value=text_message))
    mail.add_content(Content(type="text/html", value=html_message))

    # create and add the meta
    meta = {
        "type": typ,
        "friendly_from": friendly_from
    }
    mail.add_custom_arg(CustomArg(key="meta", value=json.dumps(meta)))

    # send 'er off!
    sg = current_app.config["sendgrid_api_client"]
    sg.client.mail.send.post(request_body=mail.get())

    
def _render_email(filename, **kwargs):
    # Render subject
    subject = render_template(filename+'_subject.txt', **kwargs)
    # Make sure that subject lines do not contain newlines
    subject = subject.replace('\n', ' ')
    subject = subject.replace('\r', ' ')
    # Render HTML message
    html_message = render_template(filename+'_message.html', **kwargs)
    # Render text message
    text_message = render_template(filename+'_message.txt', **kwargs)

    return (subject, html_message, text_message)

def flask_send_email(recipient, subject, html_message, text_message, typ):
    """ Send email from default sender to 'recipient' """

    class SendEmailError(Exception):
        pass

    # Make sure that Flask-Mail has been installed
    try:
        from flask_mail import Message
    except:
        raise SendEmailError("Flask-Mail has not been installed. Use 'pip install Flask-Mail' to install Flask-Mail.")

    # Make sure that Flask-Mail has been initialized
    mail_engine = current_app.extensions.get('mail', None)
    if not mail_engine:
        raise SendEmailError('Flask-Mail has not been initialized. Initialize Flask-Mail or disable USER_SEND_PASSWORD_CHANGED_EMAIL, USER_SEND_REGISTERED_EMAIL and USER_SEND_USERNAME_CHANGED_EMAIL')

    try:

        # Construct Flash-Mail message
        message = Message(subject,
                recipients=[recipient],
                html = html_message,
                body = text_message)
        mail_engine.send(message)

    # Print helpful error messages on exceptions
    except (socket.gaierror, socket.error):
        raise SendEmailError('SMTP Connection error: Check your MAIL_SERVER and MAIL_PORT settings.')
    except smtplib.SMTPAuthenticationError:
        raise SendEmailError('SMTP Authentication error: Check your MAIL_USERNAME and MAIL_PASSWORD settings.')

def get_primary_user_email(user):
    user_manager =  current_app.user_manager
    db_adapter = user_manager.db_adapter
    if db_adapter.UserEmailClass:
        user_email = db_adapter.find_first_object(db_adapter.UserEmailClass,
                user_id=int(user.get_id()),
                is_primary=True)
        return user_email
    else:
        return user


def send_confirm_email_email(user, user_email, confirm_email_link):
    # Verify certain conditions
    user_manager =  current_app.user_manager
    if not user_manager.enable_email: return
    if not user_manager.send_registered_email and not user_manager.enable_confirm_email: return

    # Retrieve email address from User or UserEmail object
    email = user_email.email if user_email else user.email
    assert(email)

    # Render subject, html message and text message
    subject, html_message, text_message = _render_email(
            user_manager.confirm_email_email_template,
            user=user,
            app_name=user_manager.app_name,
            confirm_email_link=confirm_email_link)

    # Send email message using Flask-Mail
    user_manager.send_email_function(email, subject, html_message, text_message, "confirm email")

def send_forgot_password_email(user, user_email, reset_password_link):
    # Verify certain conditions
    user_manager =  current_app.user_manager
    if not user_manager.enable_email: return
    assert user_manager.enable_forgot_password

    # Retrieve email address from User or UserEmail object
    email = user_email.email if user_email else user.email
    assert(email)

    # Render subject, html message and text message
    subject, html_message, text_message = _render_email(
            user_manager.forgot_password_email_template,
            user=user,
            app_name=user_manager.app_name,
            reset_password_link=reset_password_link)

    # Send email message using Flask-Mail
    user_manager.send_email_function(email, subject, html_message, text_message, "forgot password")

def send_password_changed_email(user):
    # Verify certain conditions
    user_manager =  current_app.user_manager
    if not user_manager.enable_email: return
    if not user_manager.send_password_changed_email: return

    # Retrieve email address from User or UserEmail object
    user_email = get_primary_user_email(user)
    assert(user_email)
    email = user_email.email
    assert(email)

    # Render subject, html message and text message
    subject, html_message, text_message = _render_email(
            user_manager.password_changed_email_template,
            user=user,
            app_name=user_manager.app_name)

    # Send email message using Flask-Mail
    user_manager.send_email_function(email, subject, html_message, text_message, "password changed")

def send_registered_email(user, user_email, confirm_email_link):    # pragma: no cover
    # Verify certain conditions
    user_manager =  current_app.user_manager
    if not user_manager.enable_email: return
    if not user_manager.send_registered_email: return

    # Retrieve email address from User or UserEmail object
    email = user_email.email if user_email else user.email
    assert(email)

    # Render subject, html message and text message
    subject, html_message, text_message = _render_email(
            user_manager.registered_email_template,
            user=user,
            app_name=user_manager.app_name,
            confirm_email_link=confirm_email_link)

    # Send email message using Flask-Mail
    user_manager.send_email_function(email, subject, html_message, text_message, "registered")

def send_username_changed_email(user):  # pragma: no cover
    # Verify certain conditions
    user_manager =  current_app.user_manager
    if not user_manager.enable_email: return
    if not user_manager.send_username_changed_email: return

    # Retrieve email address from User or UserEmail object
    user_email = get_primary_user_email(user)
    assert(user_email)
    email = user_email.email
    assert(email)

    # Render subject, html message and text message
    subject, html_message, text_message = _render_email(
            user_manager.username_changed_email_template,
            user=user,
            app_name=user_manager.app_name)

    # Send email message using Flask-Mail
    user_manager.send_email_function(email, subject, html_message, text_message, "username changed")

def send_invite_email(user, accept_invite_link):
    user_manager = current_app.user_manager
    if not user_manager.enable_email: return

    # Render subject, html message and text message
    subject, html_message, text_message = _render_email(
            user_manager.invite_email_template,
            user=user,
            app_name=user_manager.app_name,
            accept_invite_link=accept_invite_link)

    # Send email message using Flask-Mail
    user_manager.send_email_function(user.email, subject, html_message, text_message, "invite")
