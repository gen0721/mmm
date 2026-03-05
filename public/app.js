const tg = window.Telegram.WebApp;
tg.expand();
tg.ready();

// Данные (Должны приходить с сервера, пока для теста тут)
const products = [
    { id: 101, name: "Arcana Fiend", game: "DOTA 2", price: 32.50, img: "https://cdn.akamai.steamstatic.com/apps/dota2/images/dota_react/heroes/nevermore.png" },
    { id: 102, name: "Karambit Fade", game: "CS2", price: 450.00, img: "https://community.cloudflare.steamstatic.com/economy/image/-9a81dlWLwJ2UUGcVs_nsVtzdOEdtWwKGZZLQHTxDZ7I56KU0Zwwo4NUX4oFJZEHLbXH5ApeO4YmlhxYQknCRvCo04DEVlxkKgpovbSsLQJf1f_BYAJD4eO7lZKKm_S6Z-uBkz0Fv8Yp2bHAp9it2VfmqBA-NmjyJ9WdclM9Y1HY_1S-wr_o08S7v53BznVrvT5iuyj-Vno2tg" },
    { id: 103, name: "GTA V Cash 100M", game: "GTA 5", price: 12.00, img: "https://media-rockstargames-com.akamaized.net/rockstargames-newsite/img/global/games/fob/640/V.jpg" }
];

function init() {
    // Авто-смена темы (Ночь/Cyber)
    const h = new Date().getHours();
    if (h >= 6 && h < 18) {
        document.documentElement.style.setProperty('--accent', '#bc13fe'); // Фиолетовый днем
    }

    render(products);
}

function render(data) {
    const catalog = document.getElementById('catalog');
    catalog.innerHTML = data.map(p => `
        <div class="card" onclick="handleBuy(${p.id}, ${p.price})">
            <img src="${p.img}" class="game-img" alt="game">
            <span class="game-name">${p.game}</span>
            <span class="item-name">${p.name}</span>
            <span class="price">${p.price.toFixed(2)} €</span>
        </div>
    `).join('');
}

async function handleBuy(id, price) {
    tg.HapticFeedback.impactOccurred('medium');
    
    // Показываем стандартный Telegram Popup
    tg.showConfirm(`Вы подтверждаете покупку за ${price}€?`, async (confirm) => {
        if (confirm) {
            tg.MainButton.setText('ОЖИДАНИЕ ОПЛАТЫ...').show();
            
            try {
                const res = await fetch('/api/create-order', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ userId: tg.initDataUnsafe.user?.id, price: price })
                });
                const data = await res.json();
                
                if (data.url) {
                    tg.openLink(data.url); // Открываем CryptoBot
                }
            } catch (err) {
                tg.showAlert("Ошибка сервера. Попробуйте позже.");
            } finally {
                tg.MainButton.hide();
            }
        }
    });
}

// Поиск
document.getElementById('searchInput').addEventListener('input', (e) => {
    const val = e.target.value.toLowerCase();
    const filtered = products.filter(p => p.name.toLowerCase().includes(val) || p.game.toLowerCase().includes(val));
    render(filtered);
});

init();
