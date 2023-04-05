var tickets = [];
document.querySelectorAll("[data-column-id='1769'] .js-detailview").forEach(
    (v) => tickets.push(v.dataset.issueKey));
console.log(tickets.join(","));