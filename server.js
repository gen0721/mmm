const express = require('express');
const { Telegraf, Markup } = require('telegraf');
const http = require('http');
const { Server } = require('socket.io');
const axios = require('axios');
require('dotenv').config();

const app = express();
const server = http.createServer(app);
const io = new Server(server, { cors: { origin: "*" } });
const bot = new Telegraf(process.env.BOT_TOKEN);

app.use(express.json());
app.use(express.static('public'));

// Временная база данных
let db = {
    users: {},
    orders: [],
    promos: [{ code: "GIFT2026", discount: 5, limit: 100 }]
};

// --- API Crypto Bot ---
const cryptoPay = axios.create({
    baseURL: 'https://pay.crypt.bot/api/',
    headers: { 'Crypto-Pay-API-Token': process.env.CRYPTO_BOT_TOKEN }
});

// Создание заказа (Escrow)
app.post('/api/create-order', async (req, res) => {
    const { userId, price, game } = req.body;
    const commission = 1.07; // 7%
    const finalAmount = (price * commission).toFixed(2);

    try {
        const response = await cryptoPay.post('createInvoice', {
            asset: 'USDT',
            amount: finalAmount
        });
        
        const order = {
            id: response.data.result.invoice_id,
            buyerId: userId,
            amount: price,
            status: 'pending',
            url: response.data.result.pay_url
        };
        db.orders.push(order);
        res.json(order);
    } catch (e) { res.status(500).json({ error: e.message }); }
});

// Бот команды
bot.start((ctx) => {
    ctx.replyWithPhoto('https://i.imgur.com/your-image.jpg', {
        caption: `🔥 **MAGIC MARKET**\n\nИмбовый маркетплейс аккаунтов и услуг!`,
        parse_mode: 'Markdown',
        ...Markup.inlineKeyboard([[Markup.button.webApp("💎 ВОЙТИ В МАГАЗИН", process.env.APP_URL)]])
    });
});

// Админка (Промокоды)
bot.command('admin', (ctx) => {
    if (ctx.from.id == process.env.ADMIN_ID) {
        ctx.reply("👑 Панель управления", Markup.inlineKeyboard([
            [Markup.button.callback('🎟 Создать промо', 'add_promo')],
            [Markup.button.callback('⚖️ Списки заказов', 'orders_list')]
        ]));
    }
});

// --- Socket.io Чат (ОСТАВЛЯЕМ ОДИН РАЗ) ---
io.on('connection', (socket) => {
    console.log('User connected to socket');
    socket.on('join_chat', (orderId) => socket.join(orderId));
    socket.on('send_msg', (data) => io.to(data.orderId).emit('new_msg', data));
});

// --- ЗАПУСК СЕРВЕРА И БОТА (ТОЛЬКО ОДИН РАЗ) ---
const PORT = process.env.PORT || 3000;

server.listen(PORT, "0.0.0.0", () => {
    console.log(`✅ Server is running on port ${PORT}`);
    
    // Запуск бота
    bot.launch()
        .then(() => console.log('🚀 Telegram Bot is live!'))
        .catch((err) => console.error('❌ Bot launch error:', err));
});

// Обработка корректной остановки
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
