const tg = window.Telegram.WebApp;
tg.expand();

const products = [
    { name: "Global Elite", game: "CS2", price: 40, icon: "🔫" },
    { name: "Arcana SF", game: "Dota 2", price: 25, icon: "⚔️" },
    { name: "100M Cash", game: "GTA 5", price: 15, icon: "💰" }
];

function init() {
    // Смена темы по времени
    const h = new Date().getHours();
    if (h > 6 && h < 18) document.body.classList.add('day');

    const catalog = document.getElementById('catalog');
    catalog.innerHTML = products.map(p => `
        <div class="card" onclick="buyItem('${p.name}', ${p.price})">
            <div style="font-size: 24px">${p.icon}</div>
            <div style="font-size: 14px; font-weight: bold; margin-top: 5px">${p.name}</div>
            <div style="color: var(--accent); font-weight: 800">${p.price} €</div>
        </div>
    `).join('');
}

async function buyItem(name, price) {
    tg.HapticFeedback.impactOccurred('heavy');
    // Тут запрос к API на создание счета
}

init();
