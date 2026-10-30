(() => {
    const canvas = document.getElementById('contact-office-map');
    const configElement = document.getElementById('contact-map-config');
    const fallback = document.getElementById('contact-map-fallback');
    if (!canvas || !configElement || !fallback || !window.DG) return;

    const config = JSON.parse(configElement.textContent);
    const point = [config.latitude, config.longitude];
    const showFallback = () => {
        canvas.hidden = true;
        fallback.hidden = false;
    };

    window.DG.then(() => {
        try {
            canvas.hidden = false;
            const map = window.DG.map(canvas, {
                center: point,
                zoom: config.zoom,
                key: config.key,
                scrollWheelZoom: false,
            });
            const popup = document.createElement('div');
            const name = document.createElement('strong');
            name.textContent = config.name;
            popup.append(name, document.createElement('br'), document.createTextNode(config.address));
            window.DG.marker(point).addTo(map).bindPopup(popup).openPopup();
            fallback.hidden = true;
            map.invalidateSize();
            // Preserve a usable address link if authorization or map tiles fail.
            map.on('tileerror', showFallback);
            map.eachLayer((layer) => {
                if (typeof layer.getTileUrl === 'function') layer.on('tileerror', showFallback);
            });
        } catch (error) {
            showFallback();
        }
    }, showFallback);
})();
