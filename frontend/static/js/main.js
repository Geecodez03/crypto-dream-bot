document.addEventListener('DOMContentLoaded', () => {
    const connectionStatus = document.getElementById('connection-status');
    const themeToggle = document.getElementById('theme-toggle');
    const orderForm = document.getElementById('order-form');
    const orderResult = document.getElementById('order-result');
    const aiPrompt = document.getElementById('ai-prompt');
    const aiSend = document.getElementById('ai-send');
    const aiResponse = document.getElementById('ai-response');
    const activityFeed = document.getElementById('activity-feed');
    const newsFeed = document.getElementById('news-feed');
    const newsUpdated = document.getElementById('news-updated');
    const ordersUpdated = document.getElementById('orders-updated');
    const orderHistoryBody = document.querySelector('#order-history-table tbody');
    const rangeButtons = document.querySelectorAll('.range-btn');
    const balanceSource = document.getElementById('balance-source');
    const modeValue = document.getElementById('mode-value');

    const priceBtc = document.getElementById('price-btc');
    const priceEth = document.getElementById('price-eth');
    const priceBtcMeta = document.getElementById('price-btc-meta');
    const priceEthMeta = document.getElementById('price-eth-meta');
    const portfolioTotal = document.getElementById('portfolio-total');
    const portfolioMeta = document.getElementById('portfolio-meta');

    const balancesBody = document.querySelector('#balances-table tbody');
    const totalValue = document.getElementById('total-value');

    const chartState = {
        btc: { id: 'tradingview-chart-btc', symbol: 'BTC/AUD', color: '#f59e0b', series: [] },
        eth: { id: 'tradingview-chart-eth', symbol: 'ETH/AUD', color: '#10b981', series: [] },
        sol: { id: 'tradingview-chart-sol', symbol: 'SOL/AUD', color: '#60a5fa', series: [] },
    };
    const TICK_SECONDS = 10;
    const MAX_TICKS = 20000;
    const RANGE_POINTS = {
        '1h': Math.floor((60 * 60) / TICK_SECONDS),
        '24h': Math.floor((24 * 60 * 60) / TICK_SECONDS),
        '1w': Math.floor((7 * 24 * 60 * 60) / TICK_SECONDS),
        '1m': Math.floor((30 * 24 * 60 * 60) / TICK_SECONDS),
        '1y': Math.floor((365 * 24 * 60 * 60) / TICK_SECONDS),
        'all': null,
    };
    const RANGE_SECONDS = {
        '1h': 60 * 60,
        '24h': 24 * 60 * 60,
        '1w': 7 * 24 * 60 * 60,
        '1m': 30 * 24 * 60 * 60,
        '1y': 365 * 24 * 60 * 60,
        'all': null,
    };
    const CANDLE_BUCKET_SECONDS = {
        '1h': 60,
        '24h': 5 * 60,
        '1w': 30 * 60,
        '1m': 2 * 60 * 60,
        '1y': 24 * 60 * 60,
        'all': 24 * 60 * 60,
    };
    let selectedRange = '1h';
    let orderHistoryRows = [];

    let lastPrices = null;
    let liveFeedUnavailableNotified = false;

    function toCurrency(value) {
        return new Intl.NumberFormat('en-AU', {
            style: 'currency',
            currency: 'AUD',
            maximumFractionDigits: 2
        }).format(value);
    }

    function addActivity(message) {
        if (!activityFeed) {
            return;
        }

        const time = new Date().toLocaleTimeString('en-AU', { hour12: false });
        const item = document.createElement('li');
        item.textContent = `${time}  ${message}`;

        activityFeed.prepend(item);

        while (activityFeed.children.length > 6) {
            activityFeed.removeChild(activityFeed.lastChild);
        }
    }

    function setConnectionStatus(type, text) {
        if (!connectionStatus) {
            return;
        }

        connectionStatus.textContent = text;
        connectionStatus.classList.remove('status-live', 'status-waiting', 'status-error');
        connectionStatus.classList.add(type);
    }

    function showNotification(message, isError = false) {
        const notification = document.getElementById('notification');
        if (!notification) {
            return;
        }

        notification.textContent = message;
        notification.classList.remove('hidden', 'error');

        if (isError) {
            notification.classList.add('error');
        }

        setTimeout(() => {
            notification.classList.add('hidden');
        }, 3000);
    }

    function updatePriceCards(data) {
        if (!data) {
            return;
        }

        const btc = Number(data['BTC/AUD']);
        const eth = Number(data['ETH/AUD']);
        const source = data.source || 'unknown';

        if (source !== 'coinspot') {
            if (priceBtc) {
                priceBtc.textContent = '--';
                priceBtcMeta.textContent = 'CoinSpot feed unavailable';
            }

            if (priceEth) {
                priceEth.textContent = '--';
                priceEthMeta.textContent = 'Waiting for live feed';
            }

            modeValue.textContent = 'OFFLINE';
            lastPrices = null;

            if (!liveFeedUnavailableNotified) {
                showNotification('Live CoinSpot feed unavailable', true);
                addActivity('CoinSpot live feed unavailable');
                liveFeedUnavailableNotified = true;
            }
            return;
        }

        if (!Number.isNaN(btc) && priceBtc) {
            priceBtc.textContent = toCurrency(btc);
            priceBtcMeta.textContent = `Source: ${source}`;
        }

        if (!Number.isNaN(eth) && priceEth) {
            priceEth.textContent = toCurrency(eth);
            priceEthMeta.textContent = `Updated: ${new Date().toLocaleTimeString('en-AU', { hour12: false })}`;
        }

        lastPrices = { btc, eth };
    modeValue.textContent = 'LIVE';
    liveFeedUnavailableNotified = false;
    }

    async function loadHeadlines() {
        if (!newsFeed || !newsUpdated) {
            return;
        }

        try {
            const response = await fetch('/api/news');
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'News unavailable');
            }

            const headlines = Array.isArray(data.headlines) ? data.headlines : [];
            newsFeed.innerHTML = '';

            if (headlines.length === 0) {
                const item = document.createElement('li');
                item.textContent = 'No headlines available right now.';
                newsFeed.appendChild(item);
            } else {
                headlines.slice(0, 8).forEach((headline) => {
                    const item = document.createElement('li');
                    if (typeof headline === 'string') {
                        item.textContent = headline;
                        newsFeed.appendChild(item);
                        return;
                    }

                    const link = document.createElement('a');
                    link.className = 'news-link';
                    link.href = headline.url || '#';
                    link.target = '_blank';
                    link.rel = 'noopener noreferrer';
                    link.textContent = headline.title || 'Untitled headline';

                    const source = document.createElement('span');
                    source.className = 'news-source';
                    source.textContent = headline.source ? `Source: ${headline.source}` : '';

                    item.appendChild(link);
                    if (source.textContent) {
                        item.appendChild(source);
                    }
                    newsFeed.appendChild(item);
                });
            }

            newsUpdated.textContent = data.updated_at || 'Updated';
            addActivity('Crypto headlines refreshed');
        } catch (error) {
            newsFeed.innerHTML = '<li>Failed to load headlines. Check network and retry.</li>';
            newsUpdated.textContent = 'Unavailable';
            addActivity(`News feed error: ${error.message}`);
        }
    }

    function updateBalancesTable(payload) {
        if (!balancesBody || !totalValue) {
            return;
        }

        const usingLive = payload && payload.success !== false && payload.balances && payload.total_value_aud !== undefined;
        const errorMessage = payload && payload.error ? String(payload.error) : '';

        if (!usingLive) {
            balancesBody.innerHTML = '<tr><td colspan="3">Live balance unavailable.</td></tr>';
            totalValue.textContent = 'Total Value: --';
            portfolioTotal.textContent = '--';
            balanceSource.textContent = 'Unavailable';
            portfolioMeta.textContent = errorMessage || 'CoinSpot balance feed unavailable';
            return;
        }

        const data = payload;

        balancesBody.innerHTML = '';

        Object.entries(data.balances).forEach(([asset, info]) => {
            const row = document.createElement('tr');
            row.innerHTML = `<td>${asset}</td><td class="ta-right">${info.amount}</td><td class="ta-right">${toCurrency(Number(info.value_aud || 0))}</td>`;
            balancesBody.appendChild(row);
        });

        const total = Number(data.total_value_aud || 0);
        totalValue.textContent = `Total Value: ${toCurrency(total)}`;
        portfolioTotal.textContent = toCurrency(total);

        if (usingLive) {
            balanceSource.textContent = 'Live Data';
            portfolioMeta.textContent = 'Synchronized with exchange';
            if (modeValue.textContent !== 'OFFLINE') {
                modeValue.textContent = 'LIVE';
            }
        }
    }

    function formatOrderTime(value) {
        if (!value) {
            return '--';
        }

        const parsed = new Date(value.includes('UTC') ? value : value.replace(' ', 'T'));
        if (Number.isNaN(parsed.getTime())) {
            return String(value);
        }
        return parsed.toLocaleString('en-AU', { hour12: false });
    }

    function renderOrderHistory(orders) {
        if (!orderHistoryBody) {
            return;
        }

        const rows = Array.isArray(orders) ? orders.slice(0, 40) : [];
        orderHistoryRows = rows;

        if (rows.length === 0) {
            orderHistoryBody.innerHTML = '<tr><td colspan="7">No recent orders yet.</td></tr>';
            return;
        }

        orderHistoryBody.innerHTML = '';
        let runningNetAud = 0;

        rows.forEach((item) => {
            const row = document.createElement('tr');
            const side = String(item.side || 'unknown').toLowerCase();
            const status = String(item.status || 'unknown').toLowerCase();
            const totalAud = Number(item.total_aud || 0);
            const normalizedSide = side === 'buy' || side === 'sell' ? side : 'unknown';
            if (normalizedSide === 'buy') {
                runningNetAud -= totalAud;
            } else if (normalizedSide === 'sell') {
                runningNetAud += totalAud;
            }

            let netClass = 'neutral';
            if (runningNetAud > 0) {
                netClass = 'positive';
            } else if (runningNetAud < 0) {
                netClass = 'negative';
            }

            const netText = normalizedSide === 'unknown' ? '--' : toCurrency(runningNetAud);
            row.innerHTML = `
                <td>${formatOrderTime(item.time)}</td>
                <td><span class="order-side ${normalizedSide}">${normalizedSide}</span></td>
                <td>${item.market || '--'}</td>
                <td class="ta-right">${Number(item.amount || 0).toFixed(8)}</td>
                <td class="ta-right">${toCurrency(totalAud)}</td>
                <td class="ta-right"><span class="net-impact ${netClass}">${netText}</span></td>
                <td><span class="order-status ${status}">${status}</span></td>
            `;
            orderHistoryBody.appendChild(row);
        });
    }

    function prependOrderHistoryFromResult(result) {
        if (!result || !result.pair) {
            return;
        }

        const latest = {
            time: new Date().toISOString(),
            side: result.side || '--',
            market: result.pair,
            amount: Number(result.amount || 0),
            total_aud: 0,
            status: result.status || 'unknown',
            source: 'socket'
        };

        const merged = [latest, ...orderHistoryRows];
        renderOrderHistory(merged);
    }

    async function loadOrderHistory({ silent = false } = {}) {
        if (!orderHistoryBody) {
            return;
        }

        try {
            const response = await fetch('/api/order-history');
            const data = await response.json();
            if (!response.ok || !data.success) {
                throw new Error(data.error || 'Order history unavailable');
            }

            renderOrderHistory(data.orders || []);
            if (ordersUpdated) {
                ordersUpdated.textContent = data.updated_at || 'Updated';
            }
            if (!silent) {
                addActivity('Order history refreshed');
            }
        } catch (error) {
            if (orderHistoryBody) {
                orderHistoryBody.innerHTML = '<tr><td colspan="7">Failed to load order history.</td></tr>';
            }
            if (ordersUpdated) {
                ordersUpdated.textContent = 'Unavailable';
            }
            if (!silent) {
                addActivity(`Order history error: ${error.message}`);
            }
        }
    }

    async function refreshBalances({ silent = false } = {}) {
        try {
            const response = await fetch('/api/balance');
            const data = await response.json();

            if (response.ok && data.success) {
                updateBalancesTable(data);
                if (!silent) {
                    addActivity('Live balances loaded');
                }
                return;
            }

            updateBalancesTable({ success: false, error: data.error || 'CoinSpot balance feed unavailable' });
            if (!silent) {
                addActivity(`Live balances unavailable: ${data.error || 'Unknown error'}`);
            }
        } catch (error) {
            updateBalancesTable({ success: false, error: 'Balance request failed' });
            if (!silent) {
                addActivity('Balance request failed');
            }
        }
    }

    function renderChartFallback(containerId, message) {
        const element = document.getElementById(containerId);
        if (!element) {
            return;
        }
        element.innerHTML = `<div class="chart-empty">${message}</div>`;
    }

    function toY(value, min, max, height) {
        const span = Math.max(max - min, 1e-9);
        return height - ((value - min) / span) * (height - 24) - 12;
    }

    function buildLinePath(values, width, height, min, max) {
        return values
            .map((value, index) => {
                const x = values.length === 1 ? width / 2 : (index / (values.length - 1)) * width;
                const y = toY(value, min, max, height);
                return `${index === 0 ? 'M' : 'L'} ${x.toFixed(2)} ${y.toFixed(2)}`;
            })
            .join(' ');
    }

    function buildAreaPath(values, width, height, min, max) {
        if (!values || values.length === 0) {
            return '';
        }

        const linePath = buildLinePath(values, width, height, min, max);
        const lastX = values.length === 1 ? width / 2 : width;
        return `${linePath} L ${lastX.toFixed(2)} ${(height - 2).toFixed(2)} L 0 ${(height - 2).toFixed(2)} Z`;
    }

    function formatSignedPercent(value) {
        if (!Number.isFinite(value)) {
            return '0.00%';
        }
        const sign = value >= 0 ? '+' : '';
        return `${sign}${value.toFixed(2)}%`;
    }

    function computeEma(points, period = 8) {
        if (!points || points.length === 0) {
            return [];
        }

        const k = 2 / (period + 1);
        const ema = [points[0]];

        for (let i = 1; i < points.length; i += 1) {
            ema.push((points[i] * k) + (ema[i - 1] * (1 - k)));
        }

        return ema;
    }

    function buildCandles(ticks, rangeKey) {
        if (!ticks || ticks.length === 0) {
            return [];
        }

        const bucketSize = CANDLE_BUCKET_SECONDS[rangeKey] || CANDLE_BUCKET_SECONDS.all;
        const rangeSeconds = RANGE_SECONDS[rangeKey];
        const endTs = ticks[ticks.length - 1].ts;

        const visibleTicks = rangeSeconds
            ? ticks.filter((tick) => tick.ts >= (endTs - rangeSeconds))
            : ticks.slice();

        if (visibleTicks.length === 0) {
            return [];
        }

        const candles = [];
        let currentBucket = null;
        let current = null;

        visibleTicks.forEach((tick) => {
            const bucket = Math.floor(tick.ts / bucketSize) * bucketSize;
            if (bucket !== currentBucket) {
                if (current) {
                    candles.push(current);
                }
                currentBucket = bucket;
                current = {
                    ts: bucket,
                    open: tick.price,
                    high: tick.price,
                    low: tick.price,
                    close: tick.price,
                };
                return;
            }

            current.high = Math.max(current.high, tick.price);
            current.low = Math.min(current.low, tick.price);
            current.close = tick.price;
        });

        if (current) {
            candles.push(current);
        }

        return candles;
    }

    function renderLiveChart(state, series, rangeKey = selectedRange) {
        const container = document.getElementById(state.id);
        if (!container) {
            return;
        }

        const candles = buildCandles(series, rangeKey);
        if (candles.length < 2) {
            renderChartFallback(state.id, 'Waiting for enough live ticks...');
            return;
        }

        const width = 820;
        const height = 280;
        const highs = candles.map((candle) => candle.high);
        const lows = candles.map((candle) => candle.low);
        const min = Math.min(...lows);
        const max = Math.max(...highs);
        const closes = candles.map((candle) => candle.close);
        const emaSeries = computeEma(closes, 8);
        const emaPath = buildLinePath(emaSeries, width, height, min, max);
        const closePath = buildLinePath(closes, width, height, min, max);
        const closeAreaPath = buildAreaPath(closes, width, height, min, max);
        const latest = closes[closes.length - 1];
        const previous = closes[closes.length - 2] || latest;
        const firstVisible = closes[0] || latest;
        const trendUp = latest >= previous;
        const trendLabel = trendUp ? '▲ Up' : '▼ Down';
        const trendClass = trendUp ? 'trend-up' : 'trend-down';
        const netChangePct = firstVisible > 0 ? ((latest - firstVisible) / firstVisible) * 100 : 0;
        const requested = RANGE_POINTS[rangeKey];
        const hasFullWindow = requested ? series.length >= requested : true;
        const coverageLabel = hasFullWindow ? rangeKey.toUpperCase() : `${rangeKey.toUpperCase()} (partial)`;
        const candleCountLabel = `${candles.length} candles`;
        const gradientId = `close-area-${state.id}`;
        const yTop = toCurrency(max);
        const yMid = toCurrency((max + min) / 2);
        const yBottom = toCurrency(min);

        const candleCount = candles.length;
        const step = width / Math.max(candleCount, 1);
        const bodyWidth = Math.max(2, Math.min(10, step * 0.65));

        const candleSvg = candles.map((candle, index) => {
            const xCenter = (index * step) + (step / 2);
            const openY = toY(candle.open, min, max, height);
            const closeY = toY(candle.close, min, max, height);
            const highY = toY(candle.high, min, max, height);
            const lowY = toY(candle.low, min, max, height);

            const isUp = candle.close >= candle.open;
            const color = isUp ? '#10b981' : '#ef4444';
            const bodyTop = Math.min(openY, closeY);
            const bodyHeight = Math.max(1.5, Math.abs(closeY - openY));
            const bodyX = xCenter - (bodyWidth / 2);

            return `
                <line x1="${xCenter.toFixed(2)}" y1="${highY.toFixed(2)}" x2="${xCenter.toFixed(2)}" y2="${lowY.toFixed(2)}" stroke="${color}" stroke-width="1.2"></line>
                <rect x="${bodyX.toFixed(2)}" y="${bodyTop.toFixed(2)}" width="${bodyWidth.toFixed(2)}" height="${bodyHeight.toFixed(2)}" fill="${color}" opacity="0.9"></rect>
            `;
        }).join('');

        container.innerHTML = `
            <div class="chart-widget">
                <div class="chart-widget-head">
                    <span class="chart-chip">${state.symbol}</span>
                    <span class="chart-price">${toCurrency(latest)}</span>
                    <span class="chart-trend ${trendClass}">${trendLabel}</span>
                    <span class="chart-chip muted">${coverageLabel}</span>
                    <span class="chart-chip muted">${candleCountLabel}</span>
                    <span class="chart-chip ${trendClass}">${formatSignedPercent(netChangePct)}</span>
                </div>
                <div class="chart-canvas-wrap">
                    <svg viewBox="0 0 ${width} ${height}" preserveAspectRatio="none" class="chart-svg" aria-label="${state.symbol} price chart">
                        <defs>
                            <linearGradient id="${gradientId}" x1="0" y1="0" x2="0" y2="1">
                                <stop offset="0%" stop-color="${state.color}" stop-opacity="0.30"></stop>
                                <stop offset="100%" stop-color="${state.color}" stop-opacity="0.02"></stop>
                            </linearGradient>
                        </defs>
                        <line x1="0" y1="35" x2="${width}" y2="35" class="chart-grid-line"></line>
                        <line x1="0" y1="95" x2="${width}" y2="95" class="chart-grid-line"></line>
                        <line x1="0" y1="155" x2="${width}" y2="155" class="chart-grid-line"></line>
                        <line x1="0" y1="215" x2="${width}" y2="215" class="chart-grid-line"></line>
                        <path d="${closeAreaPath}" fill="url(#${gradientId})"></path>
                        <path d="${closePath}" fill="none" stroke="${state.color}" stroke-width="2" opacity="0.95"></path>
                        ${candleSvg}
                        <path d="${emaPath}" fill="none" class="chart-ema-line"></path>
                    </svg>
                    <div class="chart-y-axis">
                        <span>${yTop}</span>
                        <span>${yMid}</span>
                        <span>${yBottom}</span>
                    </div>
                </div>
            </div>
        `;
    }

    function initializeCharts() {
        renderChartFallback('tradingview-chart-btc', 'Waiting for live CoinSpot price feed...');
        renderChartFallback('tradingview-chart-eth', 'Waiting for live CoinSpot price feed...');
        renderChartFallback('tradingview-chart-sol', 'Waiting for live CoinSpot price feed...');
        addActivity('Chart panels initialized for CoinSpot live feed');
    }

    function pushChartPoint(key, value, ts) {
        const state = chartState[key];
        if (!state || Number.isNaN(value) || value <= 0) {
            return;
        }

        state.series.push({ price: value, ts });
        if (state.series.length > MAX_TICKS) {
            state.series.shift();
        }

        renderLiveChart(state, state.series, selectedRange);
    }

    function updateLiveCharts(prices) {
        if (!prices || prices.source !== 'coinspot') {
            renderChartFallback('tradingview-chart-btc', 'CoinSpot live feed unavailable.');
            renderChartFallback('tradingview-chart-eth', 'CoinSpot live feed unavailable.');
            renderChartFallback('tradingview-chart-sol', 'CoinSpot live feed unavailable.');
            return;
        }

        const tickTs = Number(prices.timestamp) || Math.floor(Date.now() / 1000);
        pushChartPoint('btc', Number(prices['BTC/AUD']), tickTs);
        pushChartPoint('eth', Number(prices['ETH/AUD']), tickTs);
        pushChartPoint('sol', Number(prices['SOL/AUD']), tickTs);
    }

    function renderAllChartsForRange(rangeKey) {
        Object.values(chartState).forEach((state) => {
            renderLiveChart(state, state.series, rangeKey);
        });
    }

    if (themeToggle) {
        themeToggle.addEventListener('click', () => {
            document.body.classList.toggle('light-theme');
            addActivity('Theme toggled');
        });
    }

    if (rangeButtons && rangeButtons.length > 0) {
        rangeButtons.forEach((button) => {
            button.addEventListener('click', () => {
                const range = button.dataset.range;
                if (!range || !RANGE_POINTS.hasOwnProperty(range)) {
                    return;
                }

                selectedRange = range;
                rangeButtons.forEach((item) => item.classList.remove('active'));
                button.classList.add('active');
                renderAllChartsForRange(selectedRange);
                addActivity(`Chart range set to ${range.toUpperCase()}`);
            });
        });
    }

    initializeCharts();
    updateBalancesTable();
    loadOrderHistory();
    loadHeadlines();
    window.setInterval(loadHeadlines, 180000);
    window.setInterval(() => loadOrderHistory({ silent: true }), 20000);
    addActivity('Dashboard initialized');

    if (typeof io === 'undefined') {
        setConnectionStatus('status-error', 'Socket unavailable');
        showNotification('Realtime connection unavailable. Running in demo mode.', true);
        addActivity('Socket client missing');
        return;
    }

    const socket = io();

    socket.on('connect', () => {
        setConnectionStatus('status-live', 'Connected');
        addActivity('Realtime socket connected');
        refreshBalances();
        loadOrderHistory({ silent: true });
    });

    socket.on('disconnect', () => {
        setConnectionStatus('status-error', 'Disconnected');
        addActivity('Realtime socket disconnected');
    });

    socket.on('connect_error', () => {
        setConnectionStatus('status-error', 'Connection error');
        addActivity('Socket connection error');
    });

    socket.on('connection_response', (data) => {
        if (data && data.prices) {
            updatePriceCards(data.prices);
            updateLiveCharts(data.prices);
            addActivity('Initial market snapshot received');
        }
    });

    socket.on('price_update', (prices) => {
        updatePriceCards(prices);
        updateLiveCharts(prices);
        if (lastPrices && !Number.isNaN(lastPrices.btc)) {
            addActivity(`Price update BTC ${toCurrency(lastPrices.btc)}`);
        }
    });

    socket.on('balances_update', (balances) => {
        updateBalancesTable(balances);
        addActivity('Balances stream updated');
    });

    window.setInterval(() => {
        refreshBalances({ silent: true });
    }, 30000);

    socket.on('order_result', (result) => {
        if (!orderResult) {
            return;
        }

        prependOrderHistoryFromResult(result);
        loadOrderHistory({ silent: true });

        if (result.status === 'filled') {
            orderResult.textContent = 'Order filled successfully';
            orderResult.className = 'result-text result-success';
            showNotification('Order placed successfully');
            addActivity('Trade filled');
            return;
        }

        const message = result.message || 'Unknown order error';
        orderResult.textContent = `Order failed: ${message}`;
        orderResult.className = 'result-text result-error';
        showNotification(`Order failed: ${message}`, true);
        addActivity(`Trade failed: ${message}`);
    });

    if (orderForm) {
        orderForm.addEventListener('submit', (event) => {
            event.preventDefault();

            const pair = document.getElementById('order-pair')?.value;
            const amount = parseFloat(document.getElementById('order-amount')?.value || '0');
            const side = document.getElementById('order-side')?.value;

            if (!pair || !side || Number.isNaN(amount) || amount <= 0) {
                showNotification('Enter a valid order amount', true);
                addActivity('Rejected invalid order form');
                return;
            }

            socket.emit('place_order', { pair, amount, side });
            addActivity(`Order submitted: ${side.toUpperCase()} ${amount} ${pair}`);
        });
    }

    if (aiSend && aiPrompt && aiResponse) {
        aiSend.addEventListener('click', async () => {
            const prompt = aiPrompt.value.trim();
            if (!prompt) {
                showNotification('Enter a prompt for the AI assistant', true);
                return;
            }

            aiSend.disabled = true;
            aiSend.textContent = 'Thinking...';
            aiResponse.textContent = 'Analyzing market context...';

            try {
                const response = await fetch('/api/ask', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ prompt })
                });

                const data = await response.json();
                if (!response.ok) {
                    throw new Error(data.error || 'AI request failed');
                }

                aiResponse.textContent = data.response || 'No response returned.';
                addActivity('AI assistant response received');
            } catch (error) {
                aiResponse.textContent = `AI unavailable: ${error.message}`;
                showNotification(`AI error: ${error.message}`, true);
                addActivity(`AI error: ${error.message}`);
            } finally {
                aiSend.disabled = false;
                aiSend.textContent = 'Ask AI';
            }
        });
    }
});
