import { fireEvent, render, screen } from '@testing-library/react';
import { describe, expect, it, vi } from 'vitest';
import { PrivateJournalInput } from './PrivateJournalInput';

const pressEnter = (element, options = {}) =>
	fireEvent.keyDown(element, { key: 'Enter', code: 'Enter', keyCode: 13, ...options });

const renderInput = (onSubmit) => {
	render(<PrivateJournalInput value="A useful note" onChange={vi.fn()} onSubmit={onSubmit} />);
	return screen.getByPlaceholderText('Write a Note');
};

describe('PrivateJournalInput', () => {
	it('adds the note with Ctrl+Enter', () => {
		const onSubmit = vi.fn();

		pressEnter(renderInput(onSubmit), { ctrlKey: true });

		expect(onSubmit).toHaveBeenCalledTimes(1);
	});

	it('adds the note with Cmd+Enter', () => {
		const onSubmit = vi.fn();

		pressEnter(renderInput(onSubmit), { metaKey: true });

		expect(onSubmit).toHaveBeenCalledTimes(1);
	});

	it('leaves Enter on its own to the field so it starts a new line', () => {
		const onSubmit = vi.fn();

		// fireEvent returns false once a listener has called preventDefault, so
		// a true here pins that the newline a browser inserts is left alone.
		const defaultAllowed = pressEnter(renderInput(onSubmit));

		expect(onSubmit).not.toHaveBeenCalled();
		expect(defaultAllowed).toBe(true);
	});

	it('keeps Shift+Enter available for a newline', () => {
		const onSubmit = vi.fn();

		pressEnter(renderInput(onSubmit), { shiftKey: true });

		expect(onSubmit).not.toHaveBeenCalled();
	});
});
