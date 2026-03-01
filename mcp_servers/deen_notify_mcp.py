"""
mcp_servers/deen_notify_mcp.py
───────────────────────────────
MCP server exposing 3 tools:
  1. search_deen_youtube    — finds a relevant English deen YouTube video
  2. send_gmail_notify      — sends HTML email with video link + schedule image
  3. send_whatsapp_notify   — sends WhatsApp message via CallMeBot free API

Required .env vars:
  YOUTUBE_API_KEY         — YouTube Data API v3 (free, 10k units/day)
  GMAIL_SENDER_EMAIL      — your Gmail address
  GMAIL_APP_PASSWORD      — Gmail App Password (not your main password)
  GMAIL_RECIPIENT_EMAIL   — destination email (can be same as sender)
  CALLMEBOT_PHONE         — e.g. "+212612345678"
  CALLMEBOT_APIKEY        — from callmebot.com (free registration)
  NOTIFY_CHANNEL          — "gmail" | "whatsapp" | "both"  (default: gmail)
"""
from __future__ import annotations
import os, json, smtplib, urllib.parse, urllib.request, base64
from email.mime.multipart import MIMEMultipart
from email.mime.text      import MIMEText
from email.mime.image     import MIMEImage
from mcp.server.fastmcp   import FastMCP

mcp = FastMCP("deen_notify")

# ─── Curated fallback videos (when no YouTube API key) ───────────────────────
CURATED = [
    {"title": "The Night of Power — What You Must Do | Omar Suleiman",
     "channel": "Yaqeen Institute", "url": "https://youtu.be/gVlEw8JZqkU"},
    {"title": "Ramadan — Change Yourself Forever | Nouman Ali Khan",
     "channel": "Bayyinah Institute", "url": "https://youtu.be/2T8HBAgkSs0"},
    {"title": "Tawakkul: Putting Your Trust in Allah | Mufti Menk",
     "channel": "Mufti Menk", "url": "https://youtu.be/wqn3pX5S8l0"},
    {"title": "The Power of Istighfar | Dr. Yasir Qadhi",
     "channel": "Yasir Qadhi", "url": "https://youtu.be/vQ-7e5jRaT4"},
    {"title": "How to Maximize the Last 10 Nights | Mufti Menk",
     "channel": "Mufti Menk", "url": "https://youtu.be/kW_5qG6pQgE"},
]


# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def search_deen_youtube(
    topic: str = "Islamic reminder",
    ramadan_day: int = 1,
    mood: str = "focused",
) -> dict:
    """
    Search YouTube for an English Islamic reminder/lecture relevant to today.

    Args:
        topic:       Theme hint e.g. "patience", "tawakkul", "Laylat al-Qadr"
        ramadan_day: Contextualises the query (last 10 nights = Qadr focus)
        mood:        tired → short clip (<10 min), otherwise medium lecture

    Returns:
        {title, channel, url, thumbnail, duration_hint, source}
    """
    api_key = os.getenv("YOUTUBE_API_KEY", "")
    if not api_key:
        video = CURATED[(ramadan_day - 1) % len(CURATED)]
        return {**video, "thumbnail": "", "duration_hint": "~15 min", "source": "curated"}

    # Build contextual query
    if ramadan_day >= 21:
        query = f"Laylat al-Qadr last 10 nights {topic} English lecture"
    else:
        query = f"Islamic reminder {topic} English Ramadan 2025"

    video_duration = "short" if mood == "tired" else "medium"
    params = urllib.parse.urlencode({
        "part": "snippet", "q": query, "type": "video",
        "videoDuration": video_duration, "relevanceLanguage": "en",
        "maxResults": 5, "key": api_key,
    })
    url = f"https://www.googleapis.com/youtube/v3/search?{params}"

    try:
        with urllib.request.urlopen(url, timeout=10) as r:
            data = json.loads(r.read())
        item    = data["items"][0]
        vid_id  = item["id"]["videoId"]
        snippet = item["snippet"]
        return {
            "title":         snippet["title"],
            "channel":       snippet["channelTitle"],
            "url":           f"https://www.youtube.com/watch?v={vid_id}",
            "thumbnail":     snippet["thumbnails"]["high"]["url"],
            "duration_hint": "short" if mood == "tired" else "~20-40 min",
            "source":        "youtube_api",
        }
    except Exception as exc:
        video = CURATED[(ramadan_day - 1) % len(CURATED)]
        return {**video, "thumbnail": "", "duration_hint": "~15 min",
                "source": "curated_fallback", "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def send_gmail_notify(
    video_title: str,
    video_url: str,
    video_channel: str,
    scheduled_time: str,
    ramadan_day: int = 1,
    schedule_image_path: str = "",
) -> dict:
    """
    Send an HTML email with the deen podcast link AND the day's schedule image.

    Args:
        video_title:         YouTube video title
        video_url:           Full YouTube URL
        video_channel:       Channel name
        scheduled_time:      "HH:MM" — when the podcast block is in the calendar
        ramadan_day:         Day number for personalisation
        schedule_image_path: Absolute path to the Canva/schedule PNG to attach
    """
    sender    = os.getenv("GMAIL_SENDER_EMAIL", "")
    password  = os.getenv("GMAIL_APP_PASSWORD", "")
    recipient = os.getenv("GMAIL_RECIPIENT_EMAIL", sender)

    if not sender or not password:
        return {"success": False, "error": "GMAIL_SENDER_EMAIL or GMAIL_APP_PASSWORD not set in .env"}

    subject = f"🎧 Day {ramadan_day} · Deen Podcast @ {scheduled_time} + Your Schedule"

    has_image = schedule_image_path and os.path.exists(schedule_image_path)
    img_tag   = '<img src="cid:schedule_card" style="width:100%;border-radius:8px;margin-top:20px;" />' \
                if has_image else ""

    html = f"""
<html><body style="margin:0;padding:0;background:#0a0a18;font-family:'Georgia',serif;">
<div style="max-width:580px;margin:30px auto;background:#12122a;border-radius:16px;
            overflow:hidden;border:1px solid #2d2d5e;">

  <!-- Header -->
  <div style="background:linear-gradient(135deg,#1e1b4b 0%,#312e81 100%);padding:28px 32px;">
    <p style="margin:0;color:#a5b4fc;font-size:12px;letter-spacing:3px;text-transform:uppercase;">
      YAWM AI · Ramadan Planner
    </p>
    <h1 style="margin:8px 0 0;color:#f5f3ff;font-size:24px;font-weight:normal;">
      يوم مبارك · Day {ramadan_day}
    </h1>
  </div>

  <!-- Podcast block -->
  <div style="padding:28px 32px;">
    <p style="margin:0 0 6px;color:#7c3aed;font-size:11px;
              text-transform:uppercase;letter-spacing:2px;">🎧 Today's Deen Podcast</p>
    <p style="margin:0 0 4px;color:#c4b5fd;font-size:13px;">
      Scheduled for <strong style="color:#f5f3ff;">{scheduled_time}</strong>
    </p>

    <div style="background:#0f0e26;border-radius:10px;padding:18px 20px;
                margin:16px 0;border-left:3px solid #7c3aed;">
      <p style="margin:0 0 4px;color:#f5f3ff;font-size:17px;font-weight:bold;
                line-height:1.4;">{video_title}</p>
      <p style="margin:0;color:#6d6a8a;font-size:13px;">{video_channel}</p>
    </div>

    <a href="{video_url}"
       style="display:block;background:linear-gradient(135deg,#7c3aed,#6d28d9);
              color:#fff;text-decoration:none;padding:14px;border-radius:10px;
              text-align:center;font-size:15px;font-weight:bold;letter-spacing:0.5px;">
      ▶&nbsp;&nbsp;Watch on YouTube
    </a>

    <!-- Schedule image -->
    {img_tag if has_image else
     '<p style="color:#4a4869;font-size:12px;margin-top:20px;text-align:center;">'
     '(Schedule image unavailable — run pipeline with Canva agent)</p>'}
  </div>

  <!-- Footer -->
  <div style="padding:16px 32px;border-top:1px solid #1e1b4b;">
    <p style="margin:0;color:#3d3a6b;font-size:11px;text-align:center;">
      بسم الله الرحمن الرحيم · YAWM AI automatically generated this plan
    </p>
  </div>
</div>
</body></html>"""

    # Build MIME message
    msg = MIMEMultipart("related")
    msg["Subject"] = subject
    msg["From"]    = sender
    msg["To"]      = recipient
    msg.attach(MIMEText(html, "html"))

    if has_image:
        with open(schedule_image_path, "rb") as f:
            img = MIMEImage(f.read())
        img.add_header("Content-ID", "<schedule_card>")
        img.add_header("Content-Disposition", "inline", filename="schedule.png")
        msg.attach(img)

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as srv:
            srv.login(sender, password)
            srv.sendmail(sender, recipient, msg.as_string())
        return {
            "success":   True,
            "recipient": recipient,
            "subject":   subject,
            "image_sent": has_image,
        }
    except Exception as exc:
        return {"success": False, "error": str(exc)}


# ─────────────────────────────────────────────────────────────────────────────
@mcp.tool()
def send_whatsapp_notify(
    video_title: str,
    video_url: str,
    scheduled_time: str,
    ramadan_day: int = 1,
) -> dict:
    """
    Send a WhatsApp message via CallMeBot (free).
    Register first at: https://www.callmebot.com/blog/free-api-whatsapp-messages/

    Args:
        video_title:    YouTube video title
        video_url:      Full YouTube URL
        scheduled_time: When the podcast is in the calendar
        ramadan_day:    Day number for personalisation
    """
    phone   = os.getenv("CALLMEBOT_PHONE", "")
    api_key = os.getenv("CALLMEBOT_APIKEY", "")

    if not phone or not api_key:
        return {"success": False,
                "error": "CALLMEBOT_PHONE or CALLMEBOT_APIKEY not set in .env"}

    text = (
        f"🕌 *YAWM AI · Ramadan Day {ramadan_day}*\n\n"
        f"🎧 *Deen Podcast @ {scheduled_time}*\n"
        f"━━━━━━━━━━━━━━\n"
        f"📺 {video_title}\n\n"
        f"▶ {video_url}\n\n"
        f"_بارك الله فيك — May Allah bless your day_ 🤲"
    )

    encoded = urllib.parse.quote(text)
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={phone}&text={encoded}&apikey={api_key}"
    )

    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            response_body = r.read().decode()
        success = "message queued" in response_body.lower() or r.status == 200
        return {"success": success, "response": response_body[:200]}
    except Exception as exc:
        return {"success": False, "error": str(exc)}


if __name__ == "__main__":
    mcp.run(transport="stdio")
