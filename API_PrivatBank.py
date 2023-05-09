import argparse
import asyncio
import aiohttp
import aiofiles
from datetime import datetime, timedelta
import json
import re
import aiopath


async def fetch_currency_rates(days):
    url = f'https://api.privatbank.ua/p24api/exchange_rates?json&date={datetime.now().strftime("%d.%m.%Y")}'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            response_json = await response.json()

    currency_rates = []
    for i in range(1, days + 1):
        date = (datetime.now() - timedelta(days=i)).strftime('%d.%m.%Y')
        url = f'https://api.privatbank.ua/p24api/exchange_rates?json&date={date}'
        async with aiohttp.ClientSession() as session:
            async with session.get(url) as response:
                response_json = await response.json()
        currency_rates.append(response_json)

    return currency_rates


def format_currency_rates(currency_rates):
    formatted_rates = []
    for response_json in currency_rates:
        rates = {'EUR': {'sale': '', 'purchase': ''}, 'USD': {'sale': '', 'purchase': ''}}
        for rate in response_json['exchangeRate']:
            if rate['currency'] == 'USD':
                rates['USD']['sale'] = rate['saleRateNB']
                rates['USD']['purchase'] = rate['purchaseRateNB']
            elif rate['currency'] == 'EUR':
                rates['EUR']['sale'] = rate['saleRateNB']
                rates['EUR']['purchase'] = rate['purchaseRateNB']
        formatted_rates.append({response_json['date']: rates})
    return formatted_rates


async def write_log(exchange_rates, log_path):
    async with aiofiles.open(log_path, mode='a', encoding='utf-8') as log_file:
        for rate in exchange_rates:
            date = list(rate.keys())[0]
            log_line = f'{date}:\n'
            log_line += f'  USD: sale - {rate[date]["USD"]["sale"]}, purchase - {rate[date]["USD"]["purchase"]}\n'
            log_line += f'  EUR: sale - {rate[date]["EUR"]["sale"]}, purchase - {rate[date]["EUR"]["purchase"]}\n'
            await log_file.write(log_line)


async def handle_exchange_command(command, log_path):
    parts = command.split()
    if len(parts) == 1:
        # current exchange rate
        currency_rates = await fetch_currency_rates(1)
        formatted_rates = format_currency_rates(currency_rates)
        response = ''
        for rates in formatted_rates:
            date = next(iter(rates))
            response += f'Exchange rates for {date}:\n'
            response += f'  USD: sale - {rates[date]["USD"]["sale"]}, purchase - {rates[date]["USD"]["purchase"]}\n'
            response += f'  EUR: sale - {rates[date]["EUR"]["sale"]}, purchase - {rates[date]["EUR"]["purchase"]}\n'
        await write_log(formatted_rates, log_path)
        return response
    elif len(parts) == 2 and re.match('^\d+$', parts[1]):
        # exchange rates for last N days
        days = int(parts[1])
        if days > 10:
            return 'Error: Maximum number of days is 10'
        currency_rates = await fetch_currency_rates(days)
        formatted_rates = format_currency_rates(currency_rates)
        response = ''
        for rates in formatted_rates:
            date = next(iter(rates))
            response += f'Exchange rates for {date}:\n'
            for currency in rates[date]:
                response += f'  {currency}: sale - {rates[date][currency]["sale"]}, purchase - {rates[date][currency]["purchase"]}\n'
        await write_log(formatted_rates, log_path)
        return response
    else:
        return 'Error: Invalid command format'


async def handle_help_command():
    response = 'List of available commands:\n'
    response += '  /exchange - show current exchange rates for USD and EUR\n'
    response += '  /exchange N - show exchange rates for USD and EUR for the last N days (up to 10)\n'
    response += '  /history - show the log of exchange rate requests\n'
    response += '  /help - show list of available commands\n'
    return response


async def handle_history_command(log_path):
    try:
        async with aiofiles.open(log_path, mode='r', encoding='utf-8') as log_file:
            log_content = await log_file.read()
    except FileNotFoundError:
        return 'Error: Log file not found'

    if not log_content:
        return 'No exchange rate requests found in log'

    return log_content


async def handle_command(command, log_path):
    parts = command.split()
    if parts[0] == '/help':
        return await handle_help_command()
    elif parts[0] == '/exchange':
        return await handle_exchange_command(command, log_path)
    elif parts[0] == '/history':
        return await handle_history_command(log_path)
    else:
        return 'Error: Invalid command'


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Currency exchange rates bot')
    parser.add_argument('--log-path', type=str, default='exchange.log', help='Path to log file')
    args = parser.parse_args()


    async def handle_client(reader, writer):
        while True:
            data = await reader.read(1024)
            if not data:
                break
            command = data.decode().strip()
            response = await handle_command(command, args.log_path)
            writer.write(response.encode())
            await writer.drain()

        writer.close()


    async def main():
        server = await asyncio.start_server(handle_client, 'localhost', 8888)
        async with server:
            await server.serve_forever()


    asyncio.run(main())
