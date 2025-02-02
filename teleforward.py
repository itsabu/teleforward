from telethon import TelegramClient, events
import os
from dotenv import load_dotenv
import asyncio
import re
import aiohttp
import json
from datetime import datetime

# Load environment variables
load_dotenv()

# Get API credentials from environment variables
API_ID = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")
CHANNEL_USERNAME = os.getenv("CHANNEL_USERNAME")  # channel name without '@'
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")

# Create the client
client = TelegramClient("session_name", API_ID, API_HASH)

# Store token data
token_data = {}


async def get_token_info(ca_address):
    """Fetch token information from DEX Screener"""
    # First get the pair information for the token
    url = f"https://api.dexscreener.com/latest/dex/tokens/{ca_address}"
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            if response.status == 200:
                data = await response.json()
                if data.get("pairs"):
                    pair = data["pairs"][0]
                    pair_address = pair.get("pairAddress")
                    pair_url = f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}"
                    async with session.get(pair_url) as pair_response:
                        if pair_response.status == 200:
                            pair_data = await pair_response.json()
                            if pair_data.get("pairs"):
                                detailed_pair = pair_data["pairs"][0]
                                return {
                                    "name": detailed_pair.get("baseToken", {}).get(
                                        "name", "Unknown"
                                    ),
                                    "symbol": detailed_pair.get("baseToken", {}).get(
                                        "symbol", "Unknown"
                                    ),
                                    "address": ca_address,
                                    "marketCap": detailed_pair.get(
                                        "marketCap", "Unknown"
                                    ),
                                    "fdv": detailed_pair.get("fdv", "Unknown"),
                                    "priceUsd": detailed_pair.get(
                                        "priceUsd", "Unknown"
                                    ),
                                    "liquidity": detailed_pair.get("liquidity", {}).get(
                                        "usd", "Unknown"
                                    ),
                                    "dex": detailed_pair.get("dexId", "Unknown"),
                                    "pairCreatedAt": detailed_pair.get(
                                        "pairCreatedAt", "Unknown"
                                    ),
                                    "timestamp": datetime.now().isoformat(),
                                }
    return None


async def save_token_data():
    """Save token data to JSON file"""
    with open("token_data.json", "w") as f:
        json.dump(token_data, f, indent=4)


async def extract_ca(text):
    """Extract CA address from message text"""
    # Updated regex to handle markdown formatting with backticks
    ca_match = re.search(r"CA:.*?`([A-Za-z0-9]+)`", text)
    return ca_match.group(1) if ca_match else None


@client.on(events.NewMessage(chats=CHANNEL_USERNAME))
async def handle_new_message(event):
    """Handle new messages from the channel"""
    message = event.message
    sender = await event.get_sender()
    sender_name = getattr(sender, "first_name", "") or getattr(
        sender, "title", "Unknown"
    )

    print("\nNew message:")
    print("-" * 50)
    print(f"Sender: {sender_name}")
    print(f"Message: {message.text}")
    print(f"Time: {message.date}")
    print("-" * 50)

    # Extract CA address if present
    if message.text:
        ca_address = await extract_ca(message.text)
        if ca_address and ca_address not in token_data:
            # Get token info
            token_info = await get_token_info(ca_address)
            if token_info:
                # Store token data
                token_data[ca_address] = token_info
                await save_token_data()

                mcap = (
                    f"${float(token_info['marketCap']):,.2f}"
                    if isinstance(token_info["marketCap"], (int, float))
                    else "Unknown"
                )
                fdv = (
                    f"${float(token_info['fdv']):,.2f}"
                    if isinstance(token_info["fdv"], (int, float))
                    else "Unknown"
                )
                liquidity = (
                    f"${float(token_info['liquidity']):,.2f}"
                    if isinstance(token_info["liquidity"], (int, float))
                    else "Unknown"
                )
                price = (
                    f"${float(token_info['priceUsd']):,.8f}"
                    if isinstance(token_info["priceUsd"], (int, float))
                    else "Unknown"
                )

                forward_message = (
                    f"🔍 New Token Detected:\n\n"
                    f"Name: {token_info['name']} (${token_info['symbol']})\n"
                    f"CA: `{ca_address}`\n"
                    f"Price: {price}\n"
                    f"Market Cap: {mcap}\n"
                    f"FDV: {fdv}\n"
                    f"Liquidity: {liquidity}\n"
                    f"DEX: {token_info['dex']}\n"
                    f"Created: <t:{token_info['pairCreatedAt']}:R>"
                )
                await client.send_message(TARGET_CHANNEL_ID, ca_address)
                print(f"Forwarded token info: {token_info}")
        elif ca_address:
            print(f"Skipping already known address: {ca_address}")


async def main():
    """Main function to run the client"""
    print("Starting client...")

    # Load existing token data if any
    global token_data
    try:
        with open("token_data.json", "r") as f:
            token_data = json.load(f)
    except FileNotFoundError:
        token_data = {}

    await client.start()

    channel = await client.get_entity(CHANNEL_USERNAME)
    print(f"Connected to channel: {channel.title}")
    print("\nListening for new messages...")

    # Keep the client running
    await client.run_until_disconnected()


if __name__ == "__main__":
    with client:
        client.loop.run_until_complete(main())
