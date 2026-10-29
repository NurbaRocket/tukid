/*
Name: 			Cleaning Services
Theme Version:	13.1.0
*/

(($ => {
    /*
	* SVG Aspect Ratio
	*/
    function aspectRatioSVG() {
		if( $(window).width() < 2000 ) {
			$('svg[preserveAspectRatio]').each(function(){
				$(this).attr('preserveAspectRatio', 'xMinYMin');
			});
		} else {
			$('svg[preserveAspectRatio]').each(function(){
				$(this).attr('preserveAspectRatio', 'none');
			});
		}
	}

    aspectRatioSVG();
    $(window).on('resize', () => {
		aspectRatioSVG();
	});
})).apply( this, [ jQuery ]);