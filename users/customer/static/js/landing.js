// Smoothly open and close FAQ questions on the landing page.
document.addEventListener('DOMContentLoaded', () => {
    const faqItems = document.querySelectorAll('.lp-faq-item');
    const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

    faqItems.forEach((item) => {
        const question = item.querySelector('summary');
        if (!question || reduceMotion) return;

        let currentAnimation = null;

        question.addEventListener('click', (event) => {
            event.preventDefault();

            // Stop an unfinished animation before starting the next one.
            if (currentAnimation) currentAnimation.cancel();

            const startingHeight = `${item.offsetHeight}px`;

            if (item.open) {
                const endingHeight = `${question.offsetHeight}px`;
                item.style.overflow = 'hidden';
                currentAnimation = item.animate(
                    [{ height: startingHeight }, { height: endingHeight }],
                    { duration: 240, easing: 'ease-out' },
                );
                currentAnimation.onfinish = () => {
                    item.open = false;
                    item.style.removeProperty('height');
                    item.style.removeProperty('overflow');
                    currentAnimation = null;
                };
            } else {
                item.open = true;
                const endingHeight = `${item.scrollHeight}px`;
                item.style.overflow = 'hidden';
                currentAnimation = item.animate(
                    [{ height: startingHeight }, { height: endingHeight }],
                    { duration: 280, easing: 'ease-out' },
                );
                currentAnimation.onfinish = () => {
                    item.style.removeProperty('height');
                    item.style.removeProperty('overflow');
                    currentAnimation = null;
                };
            }
        });
    });
});
