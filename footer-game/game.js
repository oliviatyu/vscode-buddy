const releaseVersions = [
	'1.132', '1.131', '1.130', '1.129', '1.128', '1.127', '1.126', '1.125', '1.124', '1.123',
	'1.122', '1.121', '1.120', '1.119', '1.118', '1.117', '1.116', '1.115', '1.114', '1.113',
	'1.112', '1.111'
];
const releasePlatformHeights = [118, 96, 124, 64, 110, 88, 120, 72, 104, 82];
const runnerGroundOffset = 14;
const releasePlatformGap = 40;
const releaseRunnerDesktopInstructions = 'Before starting, while paused, or after game over, use Left Arrow, Right Arrow, Home, or End to browse releases, drag the game area, or use Tab to focus a release notes link. During the game, use Space, Up Arrow, or W to jump. Press Enter to open the release notes beneath the character in a new tab. Press Escape to pause.';
const releaseRunnerTouchInstructions = 'Tap Start to play. During the game, tap the game area or use the Jump button to jump, and use Pause to stop. While idle, paused, or after game over, swipe or drag left and right to browse releases and tap a release notes link to open it in a new tab.';
const releaseRunnerReducedMotionInstructions = 'Game animation is disabled because reduced motion is enabled. Swipe or drag to browse releases, use Left Arrow, Right Arrow, Home, or End, or use Tab to focus a release notes link.';

/**
 * @typedef {{ element: HTMLImageElement, position: number, width: number, height: number }} RunnerObstacle
 * @typedef {{ element: HTMLAnchorElement, text: HTMLSpanElement, position: number, width: number, surfaceHeight: number, releaseNotesUrl: string, landed: boolean }} RunnerLabel
 * @typedef {'idle' | 'running' | 'paused' | 'gameover'} RunnerMode
 */

/**
 * @param {HTMLElement} runner
 * @param {boolean} prefersReducedMotion
 */
function initReleaseRunner(runner, prefersReducedMotion) {
	const stage = /** @type {HTMLElement | null} */ (runner.querySelector('[data-runner-stage]'));
	const player = /** @type {HTMLElement | null} */ (runner.querySelector('[data-runner-player]'));
	const labelLayer = /** @type {HTMLElement | null} */ (runner.querySelector('[data-runner-labels]'));
	const obstacleLayer = /** @type {HTMLElement | null} */ (runner.querySelector('[data-runner-obstacles]'));
	const actionButton = /** @type {HTMLButtonElement | null} */ (runner.querySelector('[data-runner-action]'));
	const actionLabel = /** @type {HTMLElement | null} */ (runner.querySelector('[data-runner-action-label]'));
	const jumpButton = /** @type {HTMLButtonElement | null} */ (runner.querySelector('[data-runner-jump]'));
	const pauseButton = /** @type {HTMLButtonElement | null} */ (runner.querySelector('[data-runner-pause]'));
	const instructions = /** @type {HTMLElement | null} */ (runner.querySelector('[data-runner-instructions]'));
	const announcer = /** @type {HTMLElement | null} */ (runner.querySelector('[data-runner-announcer]'));

	if (!stage || !player || !labelLayer || !obstacleLayer ||
		!actionButton || !actionLabel || !jumpButton || !pauseButton || !instructions || !announcer) {
		return;
	}
	if (runner.dataset.runnerInitialized === 'true') {
		return;
	}
	runner.dataset.runnerInitialized = 'true';
	const touchInstructionsQuery = window.matchMedia('(max-width: 640px), (pointer: coarse)');
	const updateRunnerInstructions = () => {
		instructions.textContent = prefersReducedMotion
			? releaseRunnerReducedMotionInstructions
			: touchInstructionsQuery.matches
				? releaseRunnerTouchInstructions
				: releaseRunnerDesktopInstructions;
	};
	updateRunnerInstructions();
	touchInstructionsQuery.addEventListener('change', updateRunnerInstructions);
	const releaseNotesLink = document.createElement('a');
	releaseNotesLink.target = '_blank';
	releaseNotesLink.rel = 'noopener noreferrer';
	releaseNotesLink.hidden = true;
	runner.appendChild(releaseNotesLink);

	const obstacles = /** @type {RunnerObstacle[]} */ ([]);
	const labels = /** @type {RunnerLabel[]} */ ([]);
	const layout = { width: 0, playerLeft: 0, playerRight: 0, maxPlayerHeight: 0 };
	let mode = 'idle';
	let animationFrame = 0;
	let previousTime = 0;
	let distance = 0;
	let speed = prefersReducedMotion ? 150 : 185;
	let jumpHeight = 0;
	let jumpVelocity = 0;
	let playerHorizontalOffset = 0;
	let nextTreeGap = 320;
	let releaseVersionIndex = 0;
	let supportedLabel = /** @type {RunnerLabel | null} */ (null);
	let platformRunStarted = false;
	let releaseBrowserOffset = 0;
	let releaseBrowserPointerId = -1;
	let releaseBrowserPointerStartX = 0;
	let releaseBrowserPointerStartOffset = 0;
	let releaseBrowserDragging = false;
	let suppressReleaseBrowserClickUntil = 0;

	runner.toggleAttribute('data-reduced-motion', prefersReducedMotion);

	/** @param {number} minimum @param {number} maximum */
	function randomBetween(minimum, maximum) {
		return minimum + Math.random() * (maximum - minimum);
	}

	function isReleaseBrowserMode() {
		return mode !== 'running';
	}

	function updateLabelAccessibility() {
		const labelsAreInteractive = isReleaseBrowserMode();
		labels.forEach((label) => {
			const isVisible = labelsAreInteractive &&
				label.position >= 0 && label.position + label.width <= layout.width;
			label.element.tabIndex = isVisible ? 0 : -1;
			label.element.toggleAttribute('aria-hidden', !isVisible);
			if (!isVisible && document.activeElement === label.element) {
				runner.focus({ preventScroll: true });
			}
		});
	}

	function refreshLayout() {
		layout.width = stage.clientWidth;
		layout.playerLeft = player.offsetLeft + 2;
		layout.playerRight = player.offsetLeft + player.offsetWidth - 2;
		layout.maxPlayerHeight = Math.max(0, stage.clientHeight - runnerGroundOffset - player.offsetHeight);
		setPlayerHeight(jumpHeight);
		labels.forEach((label) => {
			label.element.style.bottom = `${runnerGroundOffset + label.surfaceHeight - label.element.offsetHeight}px`;
		});
		if (mode === 'idle' && supportedLabel && releaseBrowserOffset === 0) {
			const positionOffset = Math.max(0, layout.playerLeft - 10) - supportedLabel.position;
			labels.forEach((label) => {
				label.position += positionOffset;
				label.element.style.transform = `translate3d(${label.position}px, 0, 0)`;
			});
		}
		if (!isReleaseBrowserMode() || releaseBrowserOffset === 0) {
			fillLabelsToStage();
		}
		if (isReleaseBrowserMode() && releaseBrowserOffset > 0) {
			scrollReleaseBrowser(releaseBrowserOffset);
		}
		updateLabelAccessibility();
	}

	/** @param {RunnerMode} nextMode */
	function setMode(nextMode) {
		mode = nextMode;
		runner.dataset.state = nextMode;
		jumpButton.hidden = nextMode !== 'running';
		pauseButton.hidden = nextMode !== 'running';
		actionButton.hidden = nextMode === 'running';
		if (isReleaseBrowserMode()) {
			stage.removeAttribute('aria-hidden');
		} else {
			stage.setAttribute('aria-hidden', 'true');
		}
		updateLabelAccessibility();
		if (!isReleaseBrowserMode()) {
			runner.classList.remove('is-dragging');
		}

		if (nextMode === 'idle') {
			actionLabel.textContent = 'Start';
		} else if (nextMode === 'paused') {
			actionLabel.textContent = 'Resume';
		} else if (nextMode === 'gameover') {
			actionLabel.textContent = 'Run again';
		}
	}

	/** @param {number} height */
	function setPlayerHeight(height) {
		jumpHeight = Math.min(Math.max(0, height), layout.maxPlayerHeight);
		player.style.transform = `translate3d(${playerHorizontalOffset}px, ${-jumpHeight}px, 0)`;
	}

	/** @param {number} offset */
	function setPlayerHorizontalOffset(offset) {
		playerHorizontalOffset = offset;
		player.style.transform = `translate3d(${playerHorizontalOffset}px, ${-jumpHeight}px, 0)`;
	}

	/** @param {number} position @returns {RunnerLabel} */
	function createLabel(position) {
		const label = document.createElement('a');
		const dot = document.createElement('span');
		const text = document.createElement('span');
		label.className = 'release-runner-label';
		label.target = '_blank';
		label.rel = 'noopener noreferrer';
		label.draggable = false;
		label.tabIndex = -1;
		label.setAttribute('aria-hidden', 'true');
		dot.className = 'release-runner-label-dot';
		label.append(dot, text);
		labelLayer.appendChild(label);
		label.addEventListener('click', (event) => {
			if (!isReleaseBrowserMode()) {
				event.preventDefault();
			}
		});

		const item = { element: label, text, position, width: 0, surfaceHeight: 0, releaseNotesUrl: '', landed: false };
		labels.push(item);
		placeLabel(item, position);
		return item;
	}

	/** @param {RunnerLabel} item @param {number} position */
	function placeLabel(item, position) {
		const versionIndex = releaseVersionIndex % releaseVersions.length;
		const version = releaseVersions[versionIndex];
		releaseVersionIndex += 1;
		item.position = position;
		item.surfaceHeight = releasePlatformHeights[versionIndex % releasePlatformHeights.length];
		item.releaseNotesUrl = `https://code.visualstudio.com/updates/v${version.replace('.', '_')}`;
		item.landed = false;
		item.text.textContent = `${version} release notes`;
		item.element.href = item.releaseNotesUrl;
		item.width = item.element.offsetWidth;
		item.element.classList.remove('is-landed');
		item.element.style.bottom = `${runnerGroundOffset + item.surfaceHeight - item.element.offsetHeight}px`;
		item.element.style.transform = `translate3d(${position}px, 0, 0)`;
	}

	function fillLabelsToStage() {
		if (!labels.length) {
			return;
		}

		let rightmostLabel = labels[0];
		for (let index = 1; index < labels.length; index += 1) {
			if (labels[index].position > rightmostLabel.position) {
				rightmostLabel = labels[index];
			}
		}

		while (rightmostLabel.position < layout.width) {
			rightmostLabel = createLabel(rightmostLabel.position + rightmostLabel.width + releasePlatformGap);
		}
		updateLabelAccessibility();
	}

	/** @param {number} position */
	function createObstacle(position) {
		const obstacle = document.createElement('img');
		const size = 24;
		obstacle.className = 'release-runner-obstacle';
		obstacle.src = './assets/release-runner-obstacle.svg';
		obstacle.alt = '';
		obstacle.width = size;
		obstacle.height = size;
		obstacle.style.width = `${size}px`;
		obstacle.style.height = `${size}px`;
		obstacle.style.transform = `translate3d(${position}px, 0, 0)`;
		obstacleLayer.appendChild(obstacle);
		obstacles.push({ element: obstacle, position, width: size, height: size });
	}

	function clearScene() {
		obstacles.splice(0).forEach((obstacle) => obstacle.element.remove());
		labels.splice(0).forEach((label) => label.element.remove());
	}

	function resetScene() {
		clearScene();
		refreshLayout();
		distance = 0;
		speed = prefersReducedMotion ? 150 : 185;
		jumpVelocity = 0;
		releaseVersionIndex = 0;
		supportedLabel = null;
		platformRunStarted = false;
		releaseBrowserOffset = 0;
		playerHorizontalOffset = 0;
		setPlayerHeight(0);
		player.classList.remove('has-crashed', 'is-airborne', 'is-on-platform');

		const firstLabel = createLabel(0);
		const firstLabelPosition = Math.max(0, layout.playerLeft - 10);
		firstLabel.position = firstLabelPosition;
		firstLabel.landed = true;
		firstLabel.element.classList.add('is-landed');
		firstLabel.element.style.transform = `translate3d(${firstLabelPosition}px, 0, 0)`;
		let rightmostLabel = firstLabel;
		while (releaseVersionIndex < releaseVersions.length) {
			rightmostLabel = createLabel(rightmostLabel.position + rightmostLabel.width + releasePlatformGap);
		}
		fillLabelsToStage();
		supportedLabel = firstLabel;
		setPlayerHeight(firstLabel.surfaceHeight);
		player.classList.add('is-on-platform');
		createObstacle(Math.max(layout.playerRight + 110, layout.width * .55));
		nextTreeGap = randomBetween(260, 380);
		updateLabelAccessibility();
	}

	/** @param {number} nextOffset */
	function scrollReleaseBrowser(nextOffset) {
		const contentRight = labels.reduce((rightmost, label) =>
			Math.max(rightmost, label.position + releaseBrowserOffset + label.width), 0);
		const maximumOffset = Math.max(0, contentRight - layout.width + 12);
		const clampedOffset = Math.min(Math.max(0, nextOffset), maximumOffset);
		const movement = clampedOffset - releaseBrowserOffset;
		releaseBrowserOffset = clampedOffset;
		labels.forEach((label) => {
			label.position -= movement;
			label.element.style.transform = `translate3d(${label.position}px, 0, 0)`;
		});
		if (supportedLabel) {
			setPlayerHorizontalOffset(-releaseBrowserOffset);
		}
		updateLabelAccessibility();
	}

	/** @param {number} movement */
	function moveLabels(movement) {
		labels.forEach((label) => {
			label.position -= movement;
			label.element.style.transform = `translate3d(${label.position}px, 0, 0)`;
		});

		labels.forEach((label) => {
			if (label.position + label.width < 0) {
				const rightmostPosition = labels.reduce((rightmost, candidate) =>
					Math.max(rightmost, candidate.position + candidate.width), 0);
				placeLabel(label, rightmostPosition + releasePlatformGap);
			}
		});
	}

	/** @param {number} movement */
	function moveObstacles(movement) {
		for (let index = obstacles.length - 1; index >= 0; index -= 1) {
			const obstacle = obstacles[index];
			obstacle.position -= movement;
			obstacle.element.style.transform = `translate3d(${obstacle.position}px, 0, 0)`;

			if (obstacle.position + obstacle.width < 0) {
				obstacle.element.remove();
				obstacles.splice(index, 1);
			}
		}

		nextTreeGap -= movement;
		if (nextTreeGap <= 0) {
			createObstacle(layout.width + 24);
			nextTreeGap = randomBetween(250, 390);
		}
	}

	/** @param {number} deltaTime */
	function updatePlayer(deltaTime) {
		if (supportedLabel) {
			const remainsSupported = supportedLabel.position < layout.playerRight &&
				supportedLabel.position + supportedLabel.width > layout.playerLeft;
			if (remainsSupported && jumpVelocity === 0) {
				setPlayerHeight(supportedLabel.surfaceHeight);
				return;
			}
			supportedLabel = null;
			player.classList.remove('is-on-platform');
			player.classList.add('is-airborne');
		}

		const previousHeight = jumpHeight;
		const nextHeight = jumpHeight + jumpVelocity * deltaTime;
		const reachedStageTop = jumpVelocity > 0 && nextHeight >= layout.maxPlayerHeight;
		const landingLabel = jumpVelocity < 0 ? labels.find((label) => {
			const overlapsPlayer = label.position < layout.playerRight &&
				label.position + label.width > layout.playerLeft;
			return overlapsPlayer && previousHeight >= label.surfaceHeight && nextHeight <= label.surfaceHeight;
		}) : null;

		if (landingLabel) {
			supportedLabel = landingLabel;
			jumpVelocity = 0;
			setPlayerHeight(landingLabel.surfaceHeight);
			player.classList.remove('is-airborne');
			player.classList.add('is-on-platform');
			if (!landingLabel.landed) {
				landingLabel.landed = true;
				landingLabel.element.classList.add('is-landed');
				announcer.textContent = `${landingLabel.text.textContent} landed. Press Enter to open.`;
			}
		} else if (nextHeight <= 0 && jumpVelocity < 0) {
			jumpVelocity = 0;
			setPlayerHeight(0);
			player.classList.remove('is-airborne', 'is-on-platform');
			if (platformRunStarted) {
				endGame();
			}
		} else {
			if (reachedStageTop) {
				jumpVelocity = 0;
			}
			setPlayerHeight(nextHeight);
			player.classList.add('is-airborne');
			player.classList.remove('is-on-platform');
		}
	}

	/** @param {number} deltaTime */
	function updateGame(deltaTime) {
		speed = (prefersReducedMotion ? 150 : 185) + Math.min(distance * .018, 115);
		const movement = speed * deltaTime;
		distance += movement;
		moveLabels(movement);
		if (mode !== 'running') {
			return;
		}
		moveObstacles(movement);
		if (!supportedLabel) {
			jumpVelocity -= 1450 * deltaTime;
		}
		updatePlayer(deltaTime);
	}

	/** @param {number} time */
	function gameLoop(time) {
		if (mode !== 'running') {
			return;
		}
		const deltaTime = previousTime ? Math.min((time - previousTime) / 1000, .032) : 0;
		previousTime = time;
		updateGame(deltaTime);
		if (mode === 'running') {
			animationFrame = window.requestAnimationFrame(gameLoop);
		}
	}

	function startGame() {
		if (mode === 'idle' || mode === 'gameover') {
			resetScene();
		}
		previousTime = 0;
		platformRunStarted = true;
		setMode('running');
		announcer.textContent = 'Game started.';
		animationFrame = window.requestAnimationFrame(gameLoop);
		runner.focus({ preventScroll: true });
	}

	function pauseGame() {
		if (mode !== 'running') {
			return;
		}
		window.cancelAnimationFrame(animationFrame);
		setMode('paused');
		announcer.textContent = 'Game paused.';
	}

	function resumeGame() {
		if (mode !== 'paused') {
			return;
		}
		scrollReleaseBrowser(0);
		setPlayerHorizontalOffset(0);
		previousTime = 0;
		setMode('running');
		announcer.textContent = 'Game resumed.';
		animationFrame = window.requestAnimationFrame(gameLoop);
		runner.focus({ preventScroll: true });
	}

	function endGame() {
		window.cancelAnimationFrame(animationFrame);
		player.classList.add('has-crashed');
		setMode('gameover');
		announcer.textContent = 'Game over. The character touched the ground.';
	}

	function jump() {
		if (jumpVelocity === 0 && (jumpHeight === 0 || supportedLabel)) {
			jumpVelocity = 640;
			platformRunStarted = true;
			supportedLabel = null;
			player.classList.remove('is-on-platform');
			player.classList.add('is-airborne');
		}
	}

	function activateRunner() {
		if (prefersReducedMotion) {
			announcer.textContent = 'Game animation is disabled because reduced motion is enabled. Browse the release notes instead.';
			return;
		}
		if (mode === 'idle' || mode === 'gameover') {
			startGame();
			jump();
		} else if (mode === 'paused') {
			resumeGame();
		} else {
			jump();
		}
	}

	function openSupportedReleaseNotes() {
		if (!supportedLabel) {
			return;
		}
		releaseNotesLink.href = supportedLabel.releaseNotesUrl;
		releaseNotesLink.click();
		announcer.textContent = `Opened ${supportedLabel.text.textContent} in a new tab.`;
	}

	actionButton.addEventListener('click', event => {
		runner.classList.toggle('is-keyboard-active', event.detail === 0);
		if (mode === 'paused') {
			resumeGame();
		} else {
			startGame();
		}
	});

	pauseButton.addEventListener('click', () => {
		pauseGame();
		actionButton.focus({ preventScroll: true });
	});
	jumpButton.addEventListener('click', event => {
		runner.classList.toggle('is-keyboard-active', event.detail === 0);
		jump();
	});
	stage.addEventListener('pointerdown', (event) => {
		if (!event.isPrimary) {
			return;
		}
		runner.classList.remove('is-keyboard-active');
		if (isReleaseBrowserMode()) {
			releaseBrowserPointerId = event.pointerId;
			releaseBrowserPointerStartX = event.clientX;
			releaseBrowserPointerStartOffset = releaseBrowserOffset;
			releaseBrowserDragging = false;
			return;
		}
		event.preventDefault();
		activateRunner();
	});
	stage.addEventListener('pointermove', (event) => {
		if (!isReleaseBrowserMode() || event.pointerId !== releaseBrowserPointerId) {
			return;
		}
		const dragDistance = event.clientX - releaseBrowserPointerStartX;
		if (!releaseBrowserDragging && Math.abs(dragDistance) < 5) {
			return;
		}
		if (!releaseBrowserDragging) {
			releaseBrowserDragging = true;
			runner.classList.add('is-dragging');
			stage.setPointerCapture(event.pointerId);
		}
		event.preventDefault();
		scrollReleaseBrowser(releaseBrowserPointerStartOffset - dragDistance);
	});

	/** @param {PointerEvent} event */
	function finishReleaseBrowserDrag(event) {
		if (event.pointerId !== releaseBrowserPointerId) {
			return;
		}
		if (releaseBrowserDragging) {
			suppressReleaseBrowserClickUntil = performance.now() + 300;
			runner.classList.remove('is-dragging');
		}
		if (stage.hasPointerCapture(event.pointerId)) {
			stage.releasePointerCapture(event.pointerId);
		}
		releaseBrowserPointerId = -1;
		releaseBrowserDragging = false;
	}

	stage.addEventListener('pointerup', finishReleaseBrowserDrag);
	stage.addEventListener('pointercancel', finishReleaseBrowserDrag);
	stage.addEventListener('click', (event) => {
		if (isReleaseBrowserMode() && performance.now() < suppressReleaseBrowserClickUntil) {
			event.preventDefault();
			event.stopPropagation();
		}
	}, true);

	runner.addEventListener('keydown', (event) => {
		if ((event.target instanceof HTMLElement && event.target.closest('button, a')) || event.repeat) {
			return;
		}
		if (isReleaseBrowserMode() && event.key === 'ArrowLeft') {
			event.preventDefault();
			scrollReleaseBrowser(releaseBrowserOffset - 80);
		} else if (isReleaseBrowserMode() && event.key === 'ArrowRight') {
			event.preventDefault();
			scrollReleaseBrowser(releaseBrowserOffset + 80);
		} else if (isReleaseBrowserMode() && event.key === 'Home') {
			event.preventDefault();
			scrollReleaseBrowser(0);
		} else if (isReleaseBrowserMode() && event.key === 'End') {
			event.preventDefault();
			scrollReleaseBrowser(Number.MAX_SAFE_INTEGER);
		} else if (event.key === 'Enter' && supportedLabel) {
			event.preventDefault();
			openSupportedReleaseNotes();
		} else if (event.key === ' ' || event.key === 'ArrowUp' || event.key.toLowerCase() === 'w') {
			event.preventDefault();
			runner.classList.add('is-keyboard-active');
			activateRunner();
		} else if (event.key === 'Escape' && mode === 'running') {
			event.preventDefault();
			pauseGame();
		}
	});

	document.addEventListener('visibilitychange', () => {
		if (document.hidden) {
			pauseGame();
		}
	});

	if ('ResizeObserver' in window) {
		new ResizeObserver(refreshLayout).observe(stage);
	}

	if ('IntersectionObserver' in window) {
		new IntersectionObserver((entries) => {
			if (!entries[0].isIntersecting) {
				pauseGame();
			}
		}, { threshold: .1 }).observe(runner);
	}

	runner.hidden = false;
	resetScene();
	setMode('idle');
	if (prefersReducedMotion) {
		actionButton.hidden = true;
		runner.setAttribute('aria-label', 'VS Code release notes browser');
		announcer.textContent = 'Game animation is disabled because reduced motion is enabled. Browse the release notes instead.';
	}
}

initReleaseRunner(document.querySelector('[data-release-runner]'), window.matchMedia('(prefers-reduced-motion: reduce)').matches);
