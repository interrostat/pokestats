 //hey datatables, hungarian-notation javascript identifiers are awful

$.fn.dataTableExt.oSort['formatted-num-asc'] = function(a,b) {
    a = a.replace( /<.*?>/g, "" );
    b = b.replace( /<.*?>/g, "" );
    var x = a.match(/\d/) ? a.replace( /[^\d\-\.]/g, "" ) : 0;
    var y = b.match(/\d/) ? b.replace( /[^\d\-\.]/g, "" ) : 0;
    return parseFloat(x) - parseFloat(y);
};
$.fn.dataTableExt.oSort['formatted-num-desc'] = function(a,b) {
    a = a.replace( /<.*?>/g, "" );
    b = b.replace( /<.*?>/g, "" );
    var x = a.match(/\d/) ? a.replace( /[^\d\-\.]/g, "" ) : 0;
    var y = b.match(/\d/) ? b.replace( /[^\d\-\.]/g, "" ) : 0;
    return parseFloat(y) - parseFloat(x);
};

function makeTable(id, skipSites) {
    $(id).each(function() {
        var number_indexes = [1,2,3,4,5,6,7];
        var name_index = [8];
        var start = 8+2;

        if(skipSites == 'pair') {
            number_indexes = [1];
            name_index = [2,3];
            start = 4;
        }
        else if(skipSites == 'triple') {
            number_indexes = [1];
            name_index = [2,3,4];
            start = 5;
        }
        else if(skipSites) {
            number_indexes = [1,2];
            name_index = [3];
            start = 3+2;
        }

        var dt = $(this).dataTable({
            aaSorting: [],
            bPaginate: false,
            bFilter: false,
            aoColumnDefs: [
                {
                    aTargets: number_indexes,
                    sType: 'formatted-num'
                },{
                    aTargets: name_index,
                    sType: 'html'
                },{
                    aTargets: [start],
                    bSortable: false
                },{
                    aTargets: [start+1, start+2, start+3, start+4, start+5, start+6, start+7, start+8, start+9],
                    sType: 'formatted-num',
                    bVisible: false
                }
            ]
        });
        
        $('.sort-group', dt).click(function() { dt.fnSort([[start+1, 'desc']]);});
        $('.sort-ambiguous', dt).click(function() { dt.fnSort([[start+2, 'desc']]);});
        $('.sort-gay', dt).click(function() { dt.fnSort([[start+3, 'desc']]);});
        
        $('.sort-male', dt).click(function() { dt.fnSort([[start+4, 'desc']]);});
        $('.sort-straight', dt).click(function() { dt.fnSort([[start+5, 'desc']]);});
        $('.sort-female', dt).click(function() { dt.fnSort([[start+6, 'desc']]);});

        $('.sort-lesbian', dt).click(function() { dt.fnSort([[start+7, 'desc']]);});
        $('.sort-allmale', dt).click(function() { dt.fnSort([[start+8, 'desc']]);});
        $('.sort-allfemale', dt).click(function() { dt.fnSort([[start+9, 'desc']]);});
    });
}
