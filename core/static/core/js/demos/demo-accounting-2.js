/*
Name:           Demo Accounting 2
Theme Version:  13.1.0
*/

(($ => {
   
    /*
	GSAP Text Reveal
	*/
    if (typeof gsap !== 'undefined') {

		if( $('.gsap-text-wrapper').length ) {

			// Animation 1
			$('.gsap-text-wrapper[data-gsap-text-anim-1]').each(function() {

				const wrapper = $(this), text = wrapper.find('>:first-child')[0];

				wrapper.css('perspective', '100px');

				const tl1Options = $.extend(true, {}, {
						duration: 1.3,
						opacity: 0,
						rotationX: -90,
						transformOrigin: '50% 50% -100',
						stagger: .25,
						ease: 'expo.out'
					},
					theme.fn.getOptions(wrapper.data('plugin-options'))
				);

				const tl1 = gsap.timeline({
				    scrollTrigger: {
				        trigger: wrapper,
				        toggleActions: 'play none none none'
				    }
				});

				tl1.from(text, tl1Options);

			});

		}

	} else {

		theme.fn.showErrorMessage('Failed to Load File', 'Failed to load: GSAP - Include the following file(s): (vendor/gsap/gsap.min.js)');

	}	

})).apply( this, [ jQuery ]);
