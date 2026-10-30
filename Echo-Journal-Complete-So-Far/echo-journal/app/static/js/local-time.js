// Shows each saved time in the reader's own time zone.
// Without JavaScript, the page keeps showing the UTC time it was sent with.
(function () {
  "use strict";
  var dateTime = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" });
  var dateOnly = new Intl.DateTimeFormat(undefined, { dateStyle: "long" });
  document.querySelectorAll("time.local-time[datetime]").forEach(function (element) {
    var when = new Date(element.getAttribute("datetime"));
    if (isNaN(when.getTime())) { return; }
    element.textContent = (element.dataset.format === "date" ? dateOnly : dateTime).format(when);
  });
})();
