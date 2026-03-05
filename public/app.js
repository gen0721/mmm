const tg = window.Telegram.WebApp;
tg.expand();

// Эмуляция базы данных
let state = {
    user: tg.initDataUnsafe.user || { first_name: "anva4ik", id: 0 },
    items: [
        { id: 1, name: "Dragonclaw Hook", price: "150€", game: "DOTA 2" },
        { id: 2, name: "AWP Dragon Lore", price: "2400€", game: "CS2" }
    ]
};

function init() {
    // Подгрузка данных пользователя
    document.getElementById('user-name-header').innerText = state.user.first_name;
    document.getElementById('profile-name').innerText = state.user.first_name;
    document.getElementById('user-id').innerText = state.user.id;
    if(state.user.photo_url) {
        document.getElementById('avatar-img').src = state.user.photo_url;
        document.getElementById('profile-pic').src = state.user.photo_url;
    }

    renderHome();
    renderCatalog();
}

function showPage(pageId, el) {
    tg.HapticFeedback.impactOccurred('light');
    
    // Переключение страниц
    document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
    document.getElementById(`page-${pageId}`).classList.add('active');

    // Обновление навбара
    if (el) {
        document.querySelectorAll('.dock-item').forEach(i => i.classList.remove('active'));
        el.classList.add('active');
    }
}

function renderHome() {
    const container = document.getElementById('fast-items');
    container.innerHTML = state.items.map(i => `
        <div class="card" onclick="openItem(${i.id})">
            <div style="font-size: 10px; color: var(--accent)">${i.game}</div>
            <div style="font-weight: bold; margin: 5px 0">${i.name}</div>
            <div>${i.price}</div>
        </div>
    `).join('');
}

function renderCatalog() {
    const container = document.getElementById('full-catalog');
    container.innerHTML = state.items.map(i => `
        <div class="card" style="height: 180px">
            <div>${i.game}</div>
            <h3>${i.name}</h3>
            <button class="buy-btn">Купить</button>
        </div>
    `).join('');
}

function openAddModal() {
    tg.HapticFeedback.notificationOccurred('success');
    tg.showPopup({
        title: 'Маркетплейс',
        message: 'Хотите выставить новый товар?',
        buttons: [{id: 'ok', type: 'default', text: 'Да, заполнить форму'}, {type: 'cancel'}]
    });
}

init();
