/* 홈 국가 검색: /assets/search.json = [국가명, slug, 영문명, 지역] */
(function () {
  var q = document.getElementById('q'), box = document.getElementById('sr');
  if (!q || !box) return;
  var data = null, loading = false;
  function load(cb) {
    if (data) return cb();
    if (loading) return;
    loading = true;
    fetch('/assets/search.json').then(function (r) { return r.json(); }).then(function (j) { data = j; cb(); }).catch(function () { loading = false; });
  }
  function norm(s) { return s.replace(/\s/g, '').toLowerCase(); }
  function render() {
    var t = norm(q.value);
    if (!t || !data) { box.style.display = 'none'; return; }
    var a = [], b = [];
    data.forEach(function (d) {
      var n = norm(d[0]), e = norm(d[2]);
      if (n.indexOf(t) === 0 || e.indexOf(t) === 0) a.push(d); else if (n.indexOf(t) > 0 || e.indexOf(t) > 0) b.push(d);
    });
    var res = a.concat(b).slice(0, 10);
    if (!res.length) { box.innerHTML = '<a href="#" onclick="return false">검색 결과가 없습니다</a>'; box.style.display = 'block'; return; }
    box.innerHTML = res.map(function (d) { return '<a href="/country/' + encodeURI(d[1]) + '/">' + d[0] + '<small>' + d[2] + ' · ' + d[3] + '</small></a>'; }).join('');
    box.style.display = 'block';
  }
  q.addEventListener('focus', function () { load(render); });
  q.addEventListener('input', function () { load(render); });
  document.addEventListener('click', function (e) { if (!box.contains(e.target) && e.target !== q) box.style.display = 'none'; });
})();
