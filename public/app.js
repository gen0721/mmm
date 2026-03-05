const tg = window.Telegram.WebApp;
tg.expand();

// Эмуляция данных (Потом заменим на запрос к серверу)
const items = [
    { id: 1, name: "Arcana PA", game: "Dota 2", price: 35, cat: "Предметы", icon: "⚔️" },
    { id: 2, name: "Global Elite", game: "CS2", price: 50, cat: "Аккаунты", icon: "🔫" },
    { id: 3, name: "100M GTA Cash", game: "GTA 5", price: 10, cat: "Услуги", icon: "💰" },
    { id: 4, name: "Prime Status", game: "CS2", price: 15, cat: "Аккаунты", icon: "🎖" },
];

function init() {
    // 1. Установка темы
    const hour = new Date().getHours();
    if (hour >= 6 && hour < 18) document.body.classList.add('day');

    // 2. Рендер каталога
    renderProducts(items);
}

function renderProducts(list) {
    const catalog = document.getElementById('catalog');
    catalog.innerHTML = list.map((p, index) => `
        <div class="card" style="animation-delay: ${index * 0.1}s" onclick="openProduct(${p.id})">
            <span class="game-badge">${p.game}</span>
            <div style="font-size: 30px; margin: 10px 0;">${p.icon}</div>
            <div style="font-weight: 600; font-size: 14px;">${p.name}</div>
            <span class="price">${p.price} €</span>
        </div>
    `).join('');
}

function openProduct(id) {
    tg.HapticFeedback.impactOccurred('medium');
    const product = items.find(i => i.id === id);
    tg.showConfirm(`Купить ${product.name} за ${product.price}€?`, (ok) => {
        if (ok) {
            // Тут вызываем твой API /api/create-order
            alert("Запрос на оплату отправлен!");
        }
    });
}

// Поиск в реальном времени
document.getElementById('searchInput').addEventListener('input', (e) => {
    const val = e.target.value.toLowerCase();
    const filtered = items.filter(i => i.name.toLowerCase().includes(val) || i.game.toLowerCase().includes(val));
    renderProducts(filtered);
});

init();
