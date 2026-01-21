import discord
from discord.ext import commands
from discord import app_commands
import sqlite3
from datetime import datetime
import os
from flask import Flask
from threading import Thread

# ================= ENV TOKEN =================
TOKEN = os.environ['TOKEN']  # Safe, do not hardcode

# ================= BOT SETUP =================
intents = discord.Intents.default()
bot = commands.Bot(command_prefix="!", intents=intents)

# ================= DATABASE =================
db = sqlite3.connect("flights.db")
cursor = db.cursor()

# Flights table
cursor.execute("""
CREATE TABLE IF NOT EXISTS flights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pilot_id INTEGER,
    flight_number TEXT,
    aircraft TEXT,
    dep TEXT,
    arr TEXT,
    gate TEXT,
    altitude TEXT,
    flight_time INTEGER,
    pic TEXT,
    fo TEXT,
    crew TEXT,
    atc TEXT,
    status TEXT,
    remarks TEXT,
    timestamp TEXT
)
""")

# Pilots table to track ranks
cursor.execute("""
CREATE TABLE IF NOT EXISTS pilots (
    pilot_id INTEGER PRIMARY KEY,
    rank TEXT DEFAULT 'Co-Pilot',
    last_promotion TEXT
)
""")
db.commit()

# ================= KEEP-ALIVE SERVER =================
app = Flask('')

@app.route('/')
def home():
    return "Bot is running!"

def run():
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.start()

keep_alive()

# ================= RANK CHECK FUNCTION =================
def check_rank(total_flights, total_minutes):
    """
    Returns (current_rank, next_rank, promotion_message)
    promotion_message is None unless user is eligible soon
    """
    # Define thresholds
    ranks = [
        {"name": "Co-Pilot", "flights": 0, "minutes": 0},
        {"name": "Elite Co-Pilot", "flights": 15, "minutes": 150},
        {"name": "Captain", "flights": 35, "minutes": 500},
        {"name": "Elite Captain", "flights": 60, "minutes": 1000},
    ]

    current_rank = "Co-Pilot"
    next_rank = None
    promotion_message = None

    for i, rank in enumerate(ranks):
        if total_flights >= rank["flights"] and total_minutes >= rank["minutes"]:
            current_rank = rank["name"]
            if i < len(ranks) - 1:
                next_rank = ranks[i + 1]["name"]
                # Check if user is close to next rank (>=80% of requirement)
                flights_req = ranks[i + 1]["flights"]
                minutes_req = ranks[i + 1]["minutes"]
                if total_flights >= flights_req * 0.8 and total_minutes >= minutes_req * 0.8:
                    promotion_message = f"🪜 You are almost eligible for {next_rank}! Prepare for the rank test."
            else:
                next_rank = None
        else:
            if i == 0:
                next_rank = ranks[i + 1]["name"]
            break

    return current_rank, next_rank, promotion_message

# ================= READY EVENT =================
@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Logged in as {bot.user}")

# ================= LOG FLIGHT =================
@bot.tree.command(name="logflight", description="Log a Qatar Airways PTFS flight")
async def logflight(
    interaction: discord.Interaction,
    flight_number: str,
    aircraft: str,
    dep: str,
    arr: str,
    gate: str,
    altitude: str,
    flight_time: int,
    fo: str = "N/A",
    crew: str = "N/A",
    atc: str = "N/A",
    status: str = "Completed",
    remarks: str = "Smooth"
):
    pic = interaction.user.mention
    timestamp = datetime.utcnow().strftime("%d %b %Y | %H:%M UTC")

    # Insert flight
    cursor.execute("""
    INSERT INTO flights VALUES (NULL,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        interaction.user.id,
        flight_number,
        aircraft,
        dep,
        arr,
        gate,
        altitude,
        flight_time,
        pic,
        fo,
        crew,
        atc,
        status,
        remarks,
        timestamp
    ))
    db.commit()

    # Update pilot rank if needed
    cursor.execute(
        "SELECT COUNT(*), SUM(flight_time) FROM flights WHERE pilot_id=?",
        (interaction.user.id,)
    )
    total_flights, total_minutes = cursor.fetchone()
    total_minutes = total_minutes or 0

    current_rank, next_rank, promotion_message = check_rank(total_flights, total_minutes)

    # Update pilot rank in pilots table
    cursor.execute("SELECT rank FROM pilots WHERE pilot_id=?", (interaction.user.id,))
    existing = cursor.fetchone()
    if existing:
        previous_rank = existing[0]
        if previous_rank != current_rank:
            cursor.execute(
                "UPDATE pilots SET rank=?, last_promotion=? WHERE pilot_id=?",
                (current_rank, timestamp, interaction.user.id)
            )
    else:
        cursor.execute(
            "INSERT INTO pilots (pilot_id, rank, last_promotion) VALUES (?,?,?)",
            (interaction.user.id, current_rank, timestamp)
        )
    db.commit()

    # Embed message
    embed = discord.Embed(
        title="✈️ Flight Logged Successfully",
        color=0x6a0dad
    )
    embed.add_field(name="Flight Number", value=flight_number, inline=True)
    embed.add_field(name="Aircraft", value=aircraft, inline=True)
    embed.add_field(name="Route", value=f"{dep} → {arr}", inline=False)
    embed.add_field(name="Gate", value=gate, inline=True)
    embed.add_field(name="Cruise Altitude", value=altitude, inline=True)
    embed.add_field(name="Flight Time", value=f"{flight_time} mins", inline=True)
    embed.add_field(name="Pilot-in-Command", value=pic, inline=False)
    embed.add_field(name="First Officer", value=fo, inline=False)
    embed.add_field(name="Cabin Crew", value=crew, inline=False)
    embed.add_field(name="ATC", value=atc, inline=False)
    embed.add_field(name="Status", value=status, inline=True)
    embed.add_field(name="Remarks", value=remarks, inline=True)
    embed.add_field(name="Current Rank", value=current_rank, inline=True)

    if next_rank:
        embed.add_field(name="Next Rank", value=next_rank, inline=True)
    if promotion_message:
        embed.add_field(name="Promotion Status", value=promotion_message, inline=False)
    else:
        embed.add_field(name="Promotion Status", value="Keep flying! Reach the next rank by completing more flights.", inline=False)

    embed.set_footer(text=f"Logged on {timestamp}")
    await interaction.response.send_message(embed=embed)

# ================= PILOT STATS =================
@bot.tree.command(name="mystats", description="View your pilot stats")
async def mystats(interaction: discord.Interaction):
    cursor.execute(
        "SELECT COUNT(*), SUM(flight_time) FROM flights WHERE pilot_id=?",
        (interaction.user.id,)
    )
    total_flights, total_minutes = cursor.fetchone()
    total_minutes = total_minutes or 0

    current_rank, next_rank, promotion_message = check_rank(total_flights, total_minutes)

    embed = discord.Embed(
        title="👨‍✈️ Pilot Statistics",
        color=0x1abc9c
    )
    embed.add_field(name="Pilot", value=interaction.user.mention)
    embed.add_field(name="Total Flights", value=total_flights)
    embed.add_field(name="Total Flight Time", value=f"{total_minutes} mins")
    embed.add_field(name="Current Rank", value=current_rank)

    if next_rank:
        embed.add_field(name="Next Rank", value=next_rank, inline=True)
    if promotion_message:
        embed.add_field(name="Promotion Status", value=promotion_message, inline=False)
    else:
        embed.add_field(name="Promotion Status", value="Keep flying! Reach the next rank by completing more flights.", inline=False)

    await interaction.response.send_message(embed=embed)

# ================= LAST FLIGHT =================
@bot.tree.command(name="lastflight", description="View your last logged flight")
async def lastflight(interaction: discord.Interaction):
    cursor.execute(
        "SELECT flight_number, aircraft, dep, arr, flight_time, timestamp FROM flights WHERE pilot_id=? ORDER BY id DESC LIMIT 1",
        (interaction.user.id,)
    )
    data = cursor.fetchone()

    if not data:
        await interaction.response.send_message("❌ No flights logged yet.")
        return

    fn, ac, dep, arr, time, ts = data

    embed = discord.Embed(
        title="🕒 Last Flight",
        color=0xf39c12
    )
    embed.add_field(name="Flight", value=fn)
    embed.add_field(name="Aircraft", value=ac)
    embed.add_field(name="Route", value=f"{dep} → {arr}")
    embed.add_field(name="Flight Time", value=f"{time} mins")
    embed.set_footer(text=f"Logged on {ts}")

    await interaction.response.send_message(embed=embed)

# ================= RANK CHECK COMMAND =================
@bot.tree.command(name="rankcheck", description="Check your current rank and promotion eligibility")
async def rankcheck(interaction: discord.Interaction):
    cursor.execute(
        "SELECT COUNT(*), SUM(flight_time) FROM flights WHERE pilot_id=?",
        (interaction.user.id,)
    )
    total_flights, total_minutes = cursor.fetchone()
    total_minutes = total_minutes or 0

    current_rank, next_rank, promotion_message = check_rank(total_flights, total_minutes)

    embed = discord.Embed(
        title="🪜 Pilot Rank Check",
        color=0x3498db
    )
    embed.add_field(name="Current Rank", value=current_rank)
    embed.add_field(name="Total Flights", value=total_flights)
    embed.add_field(name="Total Flight Minutes", value=f"{total_minutes} mins")

    if next_rank:
        embed.add_field(name="Next Rank", value=next_rank, inline=True)
    if promotion_message:
        embed.add_field(name="Promotion Status", value=promotion_message, inline=False)
    else:
        embed.add_field(name="Promotion Status", value="Keep flying! Reach the next rank by completing more flights.", inline=False)

    await interaction.response.send_message(embed=embed)

# ================= RUN BOT =================
bot.run(TOKEN)
