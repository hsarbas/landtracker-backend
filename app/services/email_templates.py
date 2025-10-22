def build_verification_email(user_email: str, verify_link: str):
    """
    Land Tracker styled verification email (green theme).
    """
    return f"""
    <html>
    <body style="background-color:#f4f5f7;font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;">
      <table align="center" width="100%" cellpadding="0" cellspacing="0">
        <tr><td align="center" style="padding:40px 0;">
          <table width="480" cellpadding="0" cellspacing="0"
                 style="background:#ffffff;border-radius:8px;overflow:hidden;
                        box-shadow:0 2px 8px rgba(0,0,0,0.08);">
            <tr><td style="padding:32px;text-align:center;">
              <img src="http://192.168.1.78:9000/assets/logo.png" 
                   alt="Land Tracker" width="80" style="margin-bottom:16px;">
              <h2 style="color:#009970;">Verify your email</h2>
              <p style="color:#4a4a4a;font-size:14px;margin-bottom:24px;">
                Hi <b>{user_email}</b>, please verify your Land Tracker account
                by clicking the button below.
              </p>
              <a href="{verify_link}" 
                 style="display:inline-block;background-color:#009970;color:#ffffff;
                        padding:12px 24px;border-radius:4px;text-decoration:none;
                        font-weight:600;">VERIFY EMAIL</a>
              <p style="font-size:13px;color:#666;margin-top:24px;">
                If the button doesn't work, copy and paste this URL:<br/>
                <a href="{verify_link}" style="color:#009970;word-break:break-all;">{verify_link}</a>
              </p>
              <p style="font-size:12px;color:#999;margin-top:32px;">
                This link expires in 24 hours.<br/>
                If you didn’t create an account, you can ignore this email.
              </p>
            </td></tr>
          </table>
        </td></tr>
      </table>
    </body>
    </html>
    """
