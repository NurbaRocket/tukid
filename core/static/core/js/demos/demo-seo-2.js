/*
Name: 			SEO 2
Theme Version:	13.1.0
*/

(($ => {
    /**
	 * Custom Simple Form Validation
	 *
	 */
    $('.custom-form-simple-validation').each(function(){
		$(this).validate({
			onkeyup: false,
			onclick: false,
			onfocusout: false,
			errorPlacement(error, element) {
				if (element.attr('type') == 'radio' || element.attr('type') == 'checkbox') {
					error.appendTo(element.closest('.form-group'));
				} else {
					error.insertAfter(element);
				}
			}
		});
	});
})).apply( this, [ jQuery ]);