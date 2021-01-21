$(function() {

    // Add a handler that triggers on assignment as well as on the specified event
    jQuery.fn.nowAndOn = function (event, handler) {
        this.each(function () {
            handler.call(this);
        });
        this.bind(event, handler);
        return this;
    };

    function showDependent(container, checkbox) {

        // Check for repositioning
        if(!$(container).data('detached')) {

            // Place the element next to the input
            $(checkbox).parent().parent().append(container);
        }

        // Show it
        $(container).show();

        // Mark all inputs
        $(container).find('input[data-required="true"], textarea[data-required="true"]').addBack().each(function(index, element) {
            $(element).attr('required', 'required');
        });
    }

    function hideDependent(container, checkbox) {

        // Show it
        $(container).hide();

        // Find all inputs
        $(container).find('input, textarea').addBack().each(function(index, element) {

            // Mark child inputs as required
            $(element).removeAttr('required');

            // Check if date input
            if($(element).hasClass('datepickerinput')) {
                // Clear the date field
                var data = JSON.parse($(element).attr('dp_config'));
                var datepickerelement = $(element).datetimepicker(data.options);
                var datepickerdata = $(datepickerelement).data("DateTimePicker");
                datepickerdata.clear();
            } else {
                // Check type
                if($(element).is(":checkbox") || $(element).is(":radio")) {
                    // Uncheck it
                    $(element).prop("checked", false);
                } else {
                    // Clear value
                    $(element).removeAttr('value');
                    $(element).val('');
                }

                // Trigger a change for any dependencies
                $(element).trigger("change");
            }
        });
    }

    $('input[data-details!=""]:checkbox').nowAndOn('change', function (){

        // Get the ID
        var checkbox = $(this);
        var _name = $(this).data('details');
        if( ! _name ) return;

        // See if checked
        var checked = this.checked;

        // Get this value
        var value = $(this).val();

        // Check for a detail input
        var enabledWhen = _name + '\=' + value;
        $('[data-enabled-when="' + enabledWhen + '"]').each(function() {

            // Get the element
            var container = $(this);

            // Move the element
            if(checked) {

                // Show it
                showDependent(container, checkbox);

            } else {

                // Hide it
                hideDependent(container, checkbox);
            }
        });
    });

    // Since radios are toggles, we have to show elements as well as
    // hide elements
    $('input[data-details!=""]:radio').nowAndOn('change', function (){

        // Get the ID
        var radio = $(this);
        var _name = $(this).data('details');
        if( ! _name ) return;

        // Get the question's value
        var value = $('input[name="' + _name + '"]:checked').val();

        // Get all dependent inputs
        var dependents = $('[data-enabled-when^="' + _name + '\="]');

        // Get all dependent inputs
        $.each(dependents, function() {

            // Get the element
            var container = $(this);

            // Get the value it depends on this radio being
            var dependentValue = $(container).data('enabled-when').replace(_name + '\=', '');

            // Compare the input's needed value to the current value
            if(dependentValue === value) {

                // Show it
                showDependent(container, radio);
            } else {

                // Hide it
                hideDependent(container, radio);
            }
        });
    });
});
