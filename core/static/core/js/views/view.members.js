/* Uses the jQuery Marquee plugin bundled with the public theme. */
((window, $) => {
    'use strict';

    $(() => {
        const root = document.querySelector('[data-member-marquee]');
        const button = document.querySelector('[data-marquee-toggle]');
        if (!root || !button || !$.isFunction($.fn.marquee)) return;

        const $root = $(root);
        const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
        const pauseReasons = new Set();
        let initialized = false;
        let resizeTimer;

        const updatePause = () => {
            if (initialized) $root.marquee(pauseReasons.size ? 'pause' : 'resume');
            const manualPause = pauseReasons.has('manual');
            button.setAttribute('aria-pressed', String(manualPause));
            button.querySelector('[data-marquee-label]').textContent = manualPause ? button.dataset.labelPlay : button.dataset.labelPause;
        };

        const configure = () => {
            if (initialized) {
                $root.marquee('destroy');
                initialized = false;
            }
            pauseReasons.clear();
            button.hidden = true;
            root.classList.remove('overflow-hidden');
            root.classList.add('overflow-auto');
            const track = root.querySelector('[data-member-track]');
            if (!track || reducedMotion.matches || track.querySelectorAll('a').length < 2 || !track.scrollWidth || !root.clientWidth) return;

            root.classList.remove('overflow-auto');
            root.classList.add('overflow-hidden');
            $root.marquee({
                speed: 30,
                gap: 0,
                delayBeforeStart: 0,
                direction: 'left',
                duplicated: true,
                duplicateCount: Math.max(1, Math.ceil(root.clientWidth / track.scrollWidth)),
                startVisible: true,
                css3easing: 'linear',
                pauseOnHover: false
            });
            initialized = true;
            button.hidden = false;

            // Only the original links take part in keyboard navigation.
            root.querySelectorAll('.js-marquee').forEach((copy, index) => {
                if (!index) return;
                copy.setAttribute('aria-hidden', 'true');
                copy.querySelectorAll('a').forEach(link => { link.tabIndex = -1; });
            });
            $root.on('mouseenter.memberLogos', () => { pauseReasons.add('hover'); updatePause(); });
            $root.on('mouseleave.memberLogos', () => { pauseReasons.delete('hover'); updatePause(); });
            $root.on('focusin.memberLogos', () => { pauseReasons.add('focus'); updatePause(); });
            $root.on('focusout.memberLogos', () => {
                window.queueMicrotask(() => {
                    if (!root.contains(document.activeElement)) pauseReasons.delete('focus');
                    updatePause();
                });
            });
            if (document.hidden) pauseReasons.add('hidden');
            updatePause();
        };

        button.addEventListener('click', () => {
            if (pauseReasons.has('manual')) pauseReasons.delete('manual');
            else pauseReasons.add('manual');
            updatePause();
        });
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) pauseReasons.add('hidden');
            else pauseReasons.delete('hidden');
            updatePause();
        });
        window.addEventListener('resize', () => {
            window.clearTimeout(resizeTimer);
            resizeTimer = window.setTimeout(configure, 200);
        });
        reducedMotion.addEventListener('change', configure);
        configure();
    });
})(window, jQuery);
