/*
Name: 			Mouse Hover Split
Theme Version:	13.1.0
*/

(($ => {
	// Mouse Hover Split
	const left = document.getElementById("side-left");
  
	const handleMove = ({clientX}) => {
	  left.style.width = `${clientX / window.innerWidth * 100}%`;
	}
  
	document.onmousemove = e => handleMove(e);
  
	document.ontouchmove = ({touches}) => handleMove(touches[0]);
  })).apply( this, [ jQuery ]);