const revealTargets = document.querySelectorAll(".reveal");

const onReveal = (entries) => {
  entries.forEach((entry) => {
    if (entry.isIntersecting) {
      entry.target.classList.add("visible");
    }
  });
};

const observer = new IntersectionObserver(onReveal, {
  threshold: 0.2,
});

revealTargets.forEach((target) => observer.observe(target));
